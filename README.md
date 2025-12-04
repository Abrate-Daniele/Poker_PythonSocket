# Poker Texas Hold'em (Socket + Tkinter)

Giocon in rete: Texas Hold'em:
- Server in Python (socket TCP + protocollo JSON)
- Client con interfaccia Tkinter


## Avvio 
1. Avvia il server:
	```bash
	python3 server/server.py
	```
2. Avvia i client (su due terminali, o due PC):
	```bash
	python3 client/client.py
	python3 client/client.py
	```
3. Nel client, inserisci Nome, Server e Porta:
	- Server locale: `localhost`
	- Porta: `5555` (default)

## Struttura progetto
```
Poker/
  server/server.py    # coordinamento partita e rete
  client/client.py    # interfaccia grafica e azioni
  poker_game.py       # carte e valutazione mani
  network_utils.py    # JSONSocket per scambio messaggi
```
