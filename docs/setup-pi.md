# Preparando o Raspberry Pi 4 (Fase 0)

Passo a passo para deixar o Pi lendo telemetria do KSP pela rede, com os problemas que já apareceram e como foram resolvidos. No cockpit, o Pi fica ligado no PC por um [cabo de rede direto](#8-cabo-de-rede-direto-até-o-pc), e a ponte da tela [abre sozinha](#9-a-ponte-da-tela-abrindo-sozinha) quando ele liga.

**Como funciona:** o mod kRPC, dentro do KSP no PC, é um **servidor**. O Pi roda um script Python que é **cliente**: ele conecta no PC pela rede (porta 50000 para comandos, 50001 para *streams*). Quem inicia a conexão é o Pi. O PC nunca precisa encontrar o Pi.

---

## 1. Gravar o cartão (no PC)

1. Baixar o [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
2. Dispositivo **Raspberry Pi 4**, sistema **Raspberry Pi OS (64-bit)** com desktop, e o cartão microSD. A gravação apaga o cartão.
3. Na personalização, preencher:
   - nome da máquina (hostname), por exemplo `ksp-cockpit`;
   - usuário e senha;
   - Wi-Fi da **mesma rede do PC**, país **BR**;
   - fuso `America/Sao_Paulo`, teclado `br`;
   - **SSH ativado**, com senha.
4. Esperar a gravação **e a verificação** terminarem antes de tirar o cartão.

O Raspberry Pi OS do Debian 13 (Trixie), com o Python 3.13, também funciona, com os mesmos passos. Nele, o `krpc` 0.6.0 instala junto o `protobuf` 7 e conecta normalmente.

## 2. Primeiro boot

Colocar o cartão no Pi (slot embaixo da placa) e ligar. O primeiro boot leva de 2 a 3 minutos e reinicia sozinho uma vez.

| LED | Significado |
|---|---|
| Vermelho fixo | Está recebendo energia. Só isso. |
| Vermelho piscando ou apagando | Fonte fraca. |
| Verde piscando irregular | Lendo o cartão, ligando normalmente. |
| Verde apagado | Não achou sistema no cartão. |
| Verde: 3 piscadas curtas + pausa, repetindo | Falha de boot. Regravar o cartão (item 1). |

O HDMI é a saída **HDMI0**, a mais perto da entrada USB-C.

## 3. Entrar no Pi pelo SSH

No terminal do Pi (com monitor e teclado), descobrir o IP e ligar o SSH, caso ele não tenha sido ativado no Imager:

```bash
hostname -I                     # IP do Pi
sudo systemctl enable --now ssh # liga o SSH agora e em todo boot
```

No PC, pelo PowerShell:

```powershell
ssh USUARIO@IP_DO_PI
```

Vale **usar o IP**: o nome `ksp-cockpit.local` funciona no Windows só às vezes. Para o IP não mudar, reservar um IP fixo para o Pi e para o PC no roteador ("reserva de DHCP").

## 4. Python do projeto

```bash
python3 -m venv ~/ksp
source ~/ksp/bin/activate   # repetir sempre que abrir o SSH; o prompt mostra (ksp)
pip install krpc pyserial   # pygame só a partir da fase 3
```

O Raspberry Pi OS atual recusa `pip install` fora de um *venv*.

Para a voz dos [avisos de voo](avisos.md) (GPWS), no alto-falante ligado no Pi:

```bash
sudo apt install -y espeak-ng alsa-utils
```

## 5. Código do projeto no Pi (git)

O repositório é público, então dá para clonar sem senha:

```bash
git --version               # se não existir: sudo apt install -y git
git clone https://github.com/Schackschuck/KSP.git ~/cockpit
```

Para atualizar depois de mudanças no GitHub:

```bash
cd ~/cockpit && git pull
```

Para **enviar** mudanças feitas no Pi (`git push`), é preciso se autenticar no GitHub, por exemplo criando uma chave SSH no Pi (`ssh-keygen -t ed25519`) e cadastrando a chave pública na conta do GitHub.

## 6. Preparar o PC

- **kRPC:** na janela do kRPC, parar o servidor, *Edit*, trocar o *Address* para **Any**, ativar *auto-accept* e iniciar de novo.
- **Rede do Windows como Privada:** Configurações → Rede e Internet → Wi-Fi → propriedades da rede → Tipo de perfil de rede → **Privada**. Com a rede marcada como Pública, o Windows bloqueia a conexão do Pi.
- **Firewall** (PowerShell como administrador):
  ```powershell
  New-NetFirewallRule -DisplayName "kRPC" -Direction Inbound -Protocol TCP -LocalPort 50000,50001 -Action Allow -Profile Private
  ```

Isso vale para o Pi na Wi-Fi de casa, como no desenvolvimento. Com o cabo direto, a rede e a regra do firewall são outras ([item 8](#8-cabo-de-rede-direto-até-o-pc)).

## 7. Testar

No Pi, com o KSP aberto e o servidor kRPC ligado:

```bash
nc -zv IP_DO_PC 50000
```

`succeeded` significa que a rede, o firewall e o servidor estão certos. O `nc` não aparece na janela do kRPC, porque só abre e fecha a porta, sem se apresentar como cliente.

Depois, o script de verdade:

```bash
python ~/cockpit/bridge/fase0_altitude.py IP_DO_PC
```

O cliente "KSP Cockpit" aparece na janela do kRPC. Se o jogo estiver fora da cena de voo, o script espera. Quando uma nave estiver na plataforma, a altitude aparece e se atualiza no terminal.

## 8. Cabo de rede direto até o PC

No cockpit, o Pi fica ligado no PC por um cabo de rede, sem passar pelo roteador. Pelo cabo, a ida e volta fica abaixo de 0,5 ms e quase não varia. Pela Wi-Fi são de 2 a 10 ms, com picos de 20 a 100 ms, e a variação atrapalha o [fly by wire](fbw.md). O PC e o Pi continuam na internet pela Wi-Fi de casa. Pelo cabo só passa o jogo.

Qualquer cabo de rede serve: o Pi 4 inverte os pares sozinho, e não precisa de cabo cruzado.

Sem roteador, ninguém distribui endereço. Os dois ganham um IP fixo, numa faixa diferente da rede de casa:

| | Endereço | Gateway |
|---|---|---|
| PC | `192.168.50.1/24` | nenhum |
| Pi | `192.168.50.2/24` | nenhum |

- **Sem gateway no cabo:** assim a internet dos dois continua pela Wi-Fi.
- **Conferir a faixa antes:** no `ipconfig`, o IPv4 do adaptador Wi-Fi não pode começar com `192.168.50`. Os roteadores da ASUS, por exemplo, vêm com `192.168.50.1`. Se começar, use outra faixa, como `192.168.60.x`, nos dois lados.

### No PC

No **PowerShell como administrador** (botão direito no PowerShell → *Executar como administrador*). Os comandos `New-...` e `Get-...` são do PowerShell: no Prompt de Comando, a janela que mostra `C:\Users\...>`, eles não existem.

```powershell
New-NetIPAddress -InterfaceAlias "Ethernet" -IPAddress 192.168.50.1 -PrefixLength 24
New-NetFirewallRule -DisplayName "kRPC cockpit" -Direction Inbound -Protocol TCP -LocalPort 50000,50001 -RemoteAddress 192.168.50.2 -Action Allow -Profile Any
```

- O nome da placa (`Ethernet`) é o que aparece no `ipconfig`, em "Adaptador Ethernet ...".
- **O firewall:** o Windows trata o cabo como "rede não identificada", com o perfil **Público**, e a regra do [item 6](#6-preparar-o-pc) só vale no Privado. A regra nova vale em qualquer perfil, mas só para o endereço do Pi.
- **O kRPC continua com o *Address* em Any.** Ele atende pelo cabo e pela Wi-Fi.

### No Pi

A conexão do `eth0` já existe. É ela que ganha o IP fixo. No Trixie, ela se chama `netplan-eth0`; no Bookworm, `Wired connection 1`. O `nmcli con show` mostra o nome.

**Pelo `nmtui`**, o jeito mais fácil:

1. `sudo nmtui` → *Edit a connection* → a conexão do `eth0`.
2. Em *IPv4 CONFIGURATION*, trocar para **Manual**: *Addresses* `192.168.50.2/24`, *Gateway* e *DNS servers* **vazios**.
3. *OK*, voltar e, em *Activate a connection*, desativar e ativar a conexão do `eth0`.

**Ou pelo `nmcli`**, trocando o nome pelo da sua conexão:

```bash
sudo nmcli con mod "netplan-eth0" ipv4.method manual ipv4.addresses 192.168.50.2/24 ipv4.gateway ""
sudo nmcli con up "netplan-eth0"
```

**Conferir:**

```bash
nmcli -g ipv4.method,ipv4.addresses,ipv4.gateway con show "netplan-eth0"
```

Tem que aparecer `manual`, `192.168.50.2/24` e uma linha vazia, que é o gateway. Depois, `sudo reboot` e, no PC, `ssh USUARIO@192.168.50.2`: o IP fixo tem que voltar sozinho. Desse ponto em diante, o SSH pode ir pelo cabo.

### Testar

Com o KSP aberto e o servidor do kRPC ligado, no Pi:

```bash
nc -zv 192.168.50.1 50000
python ~/cockpit/bridge/fase0_altitude.py 192.168.50.1
```

| Resultado do `nc` | Quer dizer |
|---|---|
| `succeeded` | A rede, o firewall e o servidor estão certos |
| `Connection refused` | O servidor do kRPC está desligado, ou com o *Address* em `localhost` |
| Fica parado até desistir | O firewall do PC: a regra de cima |

### Entrar no Pi pelo nome

O nome `.local` às vezes falha no Windows e pode ir pela Wi-Fi. Para ir sempre pelo cabo, ensine o nome ao PC:

1. Abra o Bloco de Notas como administrador e abra o arquivo `C:\Windows\System32\drivers\etc\hosts`.
2. No fim, acrescente a linha `192.168.50.2    NOME_DO_PI`. O nome é o que o `hostname` mostra no Pi.
3. Salve. Daí em diante, `ssh USUARIO@NOME_DO_PI` vai pelo cabo.

### Achar o Pi quando não se sabe o IP

A placa de rede e a Wi-Fi do Pi 4 têm o endereço físico começando com `dc-a6-32` ou `e4-5f-01`.

- **Pela Wi-Fi de casa,** no Prompt de Comando: `arp -a`. Procure esse começo; o IP está na mesma linha. O mesmo endereço físico pode aparecer com dois IPs: é o mesmo Pi, que pegou um IP novo do roteador numa religada.
- **Pelo cabo, antes do IP fixo:** sem ninguém distribuindo endereço, o Pi fica só com um endereço IPv6, `fe80::...`.
  - No Prompt de Comando: `netsh interface ipv6 show neighbors NN`. O `NN` é o número que aparece depois do `%` no "Endereço IPv6 de link local" do `ipconfig`.
  - Se aparecer uma linha `fe80::` com o endereço físico do Pi, entre com `ssh USUARIO@fe80::...%NN`.
  - Linhas como **Inalcançável** e `00-00-00-00-00-00` são de quem não respondeu. Se só houver essas, entre pela Wi-Fi para pôr o IP fixo.

## 9. A ponte da tela abrindo sozinha

O serviço [`bridge/servico/ksp-tela@.service`](../bridge/servico/ksp-tela@.service) abre a ponte da tela (`bridge/mfd.py`) quando o Pi liga.

- **A ponte espera o KSP abrir**, avisando uma vez por que ainda não conectou, e tenta de novo a cada 5 s.
- **Quando o jogo fecha**, ela fecha a conexão e espera ele abrir de novo. A tela fica em `SEM SINAL` enquanto isso.
- **Se a tela ou o painel saem da USB**, a ponte fecha, e o serviço abre ela de novo em 5 s.

O nome depois do `@` é o usuário do Pi. Os caminhos são os dos itens 4 e 5: o venv em `~/ksp` e o projeto em `~/cockpit`.

**Instalar, uma vez só** (trocando `USUARIO` pelo seu usuário):

```bash
mkdir -p ~/.config
cp ~/cockpit/bridge/servico/ksp-tela.conf ~/.config/ksp-tela.conf
sudo cp ~/cockpit/bridge/servico/ksp-tela@.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ksp-tela@USUARIO
```

**Os argumentos** ficam no `~/.config/ksp-tela.conf`, numa linha só. São os mesmos da linha de comando (`python ~/cockpit/bridge/mfd.py --help`):

```
ARGS=192.168.50.1 --celular
```

- `192.168.50.1` é o PC, pelo cabo.
- `--celular`: a tela no navegador do celular, em `http://IP_DO_PI:8000`, e a página de botões em `:8001`. O `IP_DO_PI` aqui é o da Wi-Fi de casa, porque é nela que o celular está.
- `--porta /dev/ttyUSB0`: a mikromedia, na USB do Pi, no lugar do `--celular`. O `ls /dev/ttyUSB*` mostra a porta.
- Depois de mudar o arquivo: `sudo systemctl restart ksp-tela@USUARIO`.

**Acompanhar e parar:**

```bash
journalctl -u ksp-tela@USUARIO -f                # o que a ponte escreve, ao vivo
sudo systemctl restart ksp-tela@USUARIO          # depois de um git pull com mudanças na ponte
sudo systemctl stop ksp-tela@USUARIO             # para até o próximo boot
sudo systemctl disable --now ksp-tela@USUARIO    # para de vez
```

- **Para rodar a ponte na mão** (para testar outra coisa), pare o serviço antes. As portas 8000 e 8001 e a serial só abrem num programa de cada vez.
- **Se o próprio `.service` mudar** num `git pull`, copie ele de novo para `/etc/systemd/system/` e rode `sudo systemctl daemon-reload`.
- **Se a voz dos avisos sair na mão e não pelo serviço**, escolha o alto-falante no `ARGS`, por exemplo `--voz plughw:1,0`. O `aplay -l` lista os alto-falantes.
- **Com o cabo puxado ou o PC desligado sem fechar o jogo**, a conexão não cai na hora. O Linux pode levar vários minutos para desistir dela, e, se o cabo voltar antes disso, a conexão continua. Para não esperar: `sudo systemctl restart ksp-tela@USUARIO`.

## Problemas já encontrados

| Sintoma | Causa | Solução |
|---|---|---|
| LED verde com 3 piscadas curtas + pausa, nada no HDMI | Cartão sem sistema ou gravação ruim | Regravar com o Imager e esperar a verificação |
| `ping` do Pi para o PC não responde | O Windows bloqueia `ping` de entrada por padrão | Normal. Testar com `nc` (item 7) |
| `ping 192.168.1.1` → "Host de destino inacessível" | O roteador não fica nesse endereço | Ver o "Gateway Padrão" no `ipconfig`. Não afeta o projeto |
| `ssh` → `Connection refused` | SSH desligado no Pi | `sudo systemctl enable --now ssh` |
| `ssh` → `Could not resolve hostname ksp-cockpit.local` | Nomes `.local` são instáveis no Windows | Usar o IP |
| `sudo apt full-upgrade` com previsão de horas | Rede lenta. A atualização não é necessária para o projeto | `Ctrl+C` enquanto ainda está baixando (`Get:`) é seguro. Rodar depois, no terminal do próprio Pi |
| Conexão do Pi não chega no kRPC | Rede do Windows marcada como Pública | Mudar para Privada (item 6) |
| `-bash: ./script.py: Permission denied` | Faltou o `python` na frente | `python script.py` |
| `ValueError: Value cannot be null. Parameter name: vessel` | Jogo fora da cena de voo (KSC, hangar, menu) | Lançar uma nave. O `fase0_altitude.py` já espera sozinho |
| `ssh` no `192.168.50.1` → `Connection refused` | Esse é o IP do PC, e o Windows não tem servidor SSH | O Pi é o `192.168.50.2` (item 8) |
| `'Get-NetNeighbor' não é reconhecido como um comando interno` | A janela é o Prompt de Comando, e o comando é do PowerShell | Abrir o PowerShell, ou usar o equivalente do Prompt de Comando (item 8) |
| `nmtui` → `nm-CRITICAL ... assertion '<dropped>' failed` | Defeito do próprio `nmtui` | Ignorar: a edição funciona |
| `source ~/ksp/bin/activate` → `No such file or directory` | O venv e o projeto não foram instalados neste Pi, ou neste usuário | Itens 4 e 5 |
| A ponte repete `recusou a conexão` | O KSP está fechado, ou o servidor do kRPC está desligado | Abrir o jogo: a ponte conecta sozinha em até 5 s |

## Manutenção

- **Desligar sempre pelo comando**, nunca puxando da tomada, para não corromper o cartão:
  ```bash
  sudo shutdown now
  ```
  Tirar da tomada só depois que o LED verde parar.
- **Atualizar o sistema** de vez em quando, direto no terminal do Pi (não pelo SSH, para não interromper se a conexão cair):
  ```bash
  sudo apt update && sudo apt full-upgrade -y
  sudo reboot
  ```
