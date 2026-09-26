# Preparando o Raspberry Pi 4 (Fase 0)

Passo a passo para deixar o Pi lendo telemetria do KSP pela rede, com os problemas que já apareceram e como foram resolvidos.

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
