"""O celular como tela multifunção: a ponte serve uma página para o navegador.

A página (celular/index.html) faz no celular o papel do firmware da
mikromedia: recebe as mensagens do protocolo, desenha a tela e manda os
toques de volta. Para a ponte, é só mais uma tela com enviar() e linhas(),
como o simulador e a placa.

As mensagens viajam pelo Wi-Fi, por HTTP:
- ponte → celular: GET /eventos abre um fluxo "Server-Sent Events" que fica
  aberto; cada mensagem do protocolo vira um evento;
- celular → ponte: POST /linha, com uma linha do protocolo no corpo (READY ao
  abrir a página, TOQUE <nome>, ERR <linha>).

Só usa a biblioteca padrão do Python.
"""

import http.server
import pathlib
import queue
import socket
import threading

PAGINA = pathlib.Path(__file__).with_name("celular") / "index.html"
MAX_CORPO = 64          # bytes: uma linha do protocolo tem no máximo 31 caracteres
PING = 10               # s sem mensagem: manda um comentário para a conexão não cair
MAX_FILA = 500          # mensagens guardadas para um celular que parou de ler (tela apagada)


def endereco_local():
    """O IP deste computador na rede local, para mostrar ao usuário."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # Não manda nada: só faz o sistema escolher a interface de rede.
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "IP-DO-COMPUTADOR"


class TelaCelular:
    """A tela no navegador do celular, com a mesma interface da classe Painel."""

    def __init__(self, porta=8000):
        self._recebidas = queue.Queue()   # celular → ponte
        self._clientes = set()            # ponte → celular: uma fila por página aberta
        self._trava = threading.Lock()
        self._parar = threading.Event()

        self._servidor = http.server.ThreadingHTTPServer(("0.0.0.0", porta), _Pedido)
        self._servidor.daemon_threads = True
        self._servidor.tela = self
        threading.Thread(target=self._servidor.serve_forever, daemon=True).start()

        print(f"Abra no navegador do celular: http://{endereco_local()}:{porta}")
        print("(o celular precisa estar no mesmo Wi-Fi que este computador)")

    def enviar(self, mensagem):
        """Ponte → celular. Sem celular conectado, a mensagem se perde, como
        numa serial sem ninguém do outro lado."""
        with self._trava:
            for fila in self._clientes:
                try:
                    fila.put_nowait(mensagem)
                except queue.Full:
                    pass

    def linhas(self):
        """Celular → ponte: as linhas que chegaram desde a última chamada."""
        linhas = []
        while True:
            try:
                linhas.append(self._recebidas.get_nowait())
            except queue.Empty:
                return linhas

    def esperar_ready(self):
        return True

    def fechar(self):
        self._parar.set()
        self._servidor.shutdown()
        self._servidor.server_close()


class _Pedido(http.server.BaseHTTPRequestHandler):
    """Atende um pedido do navegador. Cada pedido roda na sua própria thread."""

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._pagina()
        elif self.path == "/eventos":
            self._eventos()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/linha":
            self.send_error(404)
            return
        tamanho = int(self.headers.get("Content-Length") or 0)
        if tamanho > MAX_CORPO:
            self.send_error(413)
            return
        linha = self.rfile.read(tamanho).decode("ascii", errors="replace").strip()
        if linha:
            self.server.tela._recebidas.put(linha)
        self.send_response(204)
        self.end_headers()

    def _pagina(self):
        corpo = PAGINA.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _eventos(self):
        """Fica mandando as mensagens da ponte até o celular desconectar."""
        tela = self.server.tela
        fila = queue.Queue(MAX_FILA)
        with tela._trava:
            tela._clientes.add(fila)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            while not tela._parar.is_set():
                try:
                    linhas = [fila.get(timeout=PING)]
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    continue
                # Junta o que já estiver na fila num envio só.
                while True:
                    try:
                        linhas.append(fila.get_nowait())
                    except queue.Empty:
                        break
                eventos = "".join(f"data: {linha}\n\n" for linha in linhas)
                self.wfile.write(eventos.encode("ascii", errors="replace"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # a página foi fechada, ou o celular saiu do Wi-Fi
        finally:
            with tela._trava:
                tela._clientes.discard(fila)

    def log_message(self, formato, *args):
        pass  # sem uma linha no terminal para cada toque
