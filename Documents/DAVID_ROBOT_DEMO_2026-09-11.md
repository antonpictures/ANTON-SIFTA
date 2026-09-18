# David: demonstratia roverului pentru integrarea SIFTA

Sursa privata: `/Users/ioanganton/Downloads/WhatsApp Video 2026-09-11 at 10.37.40.mp4`.
Durata masurata: 113.267 secunde; imagine 848 x 478; pista audio 48 kHz.
Analiza: cadre esantionate la circa 10 secunde si transcriere locala Whisper
small, limba romana. Transcrierea automata contine erori; textul de mai jos
este o reformulare cu sensul clar, nu citat cuvant cu cuvant.

## Continutul demonstratiei

| Interval | Explicatia lui David / ce se observa |
|---|---|
| 00:00-00:09 | Prezinta robotul, senzorul LiDAR care scaneaza cu laser si camera montata deasupra. |
| 00:09-00:15 | Apasa un buton pentru afisarea adresei IP. Pe modul se vede eticheta LILYGO T-Camera. |
| 00:15-00:25 | Deschide adresa locala pe tableta: interfata arata imaginea camerei roverului. |
| 00:25-00:37 | Explica graficul LiDAR; introduce mana in fata senzorului si indica punctele fata de linia centrala punctata. |
| 00:37-00:54 | Foloseste controlul tactil stanga/dreapta pentru directie, in modul manual/jog. Graficul afiseaza calea estimata. |
| 00:54-01:06 | Selecteaza modul autonom. Avertizeaza ca demonstratia poate sa nu reuseasca din prima; o parte a explicatiei audio nu se transcrie clar. |
| 01:06-01:34 | Spune ca robotul merge si ocoleste obstacole local, fara tokeni. Explica faptul ca se opreste daca nu mai are loc sa continue. Cadrele arata roverul langa obstacole de carton si schimbarea imaginii camerei. |
| 01:34-01:46 | Explica alegerea unei cai si oprirea cand apar puncte in zona interzisa. |
| 01:46-01:52 | Indica pe grafic zona de protectie: daca apar puncte acolo, robotul se opreste. Incheie demonstratia. |

## Ce inseamna pentru SIFTA

David are deja o interfata web de camera/control si un controler local care,
conform demonstratiei sale, foloseste LiDAR pentru navigare si oprire. Nu trebuie
sa reconstruim aceasta baza si nici sa inlocuim oprirea locala cu un raspuns LLM.
Filmul demonstreaza un prototip; nu certifica toate conditiile de siguranta.

Arhitectura propusa:

`camera + LiDAR + stare rover -> adaptor pe Mac -> Alice/SIFTA -> obiectiv validat -> controler rover`

`stigmergicoin.com` ramane suprafata de dialog, vizualizare si comenzi ale
proprietarului. Daca roverul livreaza deja camera si senzori, telefonul poate fi
doar ecranul de control. Montarea unui iPhone este optionala pentru acesti senzori;
ARKit ar necesita separat aplicatie nativa si calibrare.

## Luna: integrare concreta, dupa primirea protocolului

1. Obtine de la David firmware-ul/repo-ul, modelul exact al placii si al LiDAR-ului,
   endpoint-ul camerei, formatul scanarii, unitatile, axele si frecventele.
2. Obtine mesajele pentru directie/viteza, stop, manual/auto, confirmari si ce face
   controlerul la pierderea conexiunii. Nu ghici endpoint-uri din adresa IP filmata.
3. Construieste un adaptor read-only cu mostre sintetice, apoi citeste camera,
   LiDAR, modul curent si starea opririi. Inregistreaza sursa si timpul fiecaruia.
4. Sincronizeaza pachetele audio/video/LiDAR folosind intervale si domenii de ceas.
   Un cadru si un sunet apropiate in timp nu demonstreaza aceeasi sursa fizica.
5. Trimite descrieri si obiective prin SIFTA; valideaza comenzile mai intai in
   simulator, cu secventa, expirare, confirmare, anulare si watchdog local.
6. Abia apoi verifica o miscare scurta autorizata, oprirea si feedback-ul real.

Necunoscute: protocolul transportului, firmware-ul, calibrarea, odometria,
autentificarea, limitele fizice si comportamentul la defect. Un grafic LiDAR local
nu este dovada unei harti persistente, ARKit, SLAM complet sau integrare SIFTA.

## Clarificare proprietar 2026-09-13: doua apartamente, prin internet

Obiectivul este ca masinuta sa circule prin apartamentul lui David si sa discute
cu David, in timp ce SIFTA ruleaza pe Mac-ul lui George, in alt apartament.
"Adaptor pe Mac" din schema initiala trebuie completat cu o punte locala la David
(sau transport securizat direct din firmware, daca este suportat). Puntea deschide
conexiunea spre stigmergicoin.com; nu presupunem acces direct intre retelele locale.
Camera/LiDAR si oprirea raman locale roverului. Telefonul poate asigura microfonul
si difuzorul daca acestea lipsesc. Conectarea nu inseamna armare automata.
Planul executabil si testele sunt la inceputul
Documents/WCT_CREDIT_SAVING_HANDOFF_2026-09-09.md, sectiunea
"David's rover drives and chats in his apartment". Integrarea WAN ramane de probat.

## Mesajele lui David furnizate de proprietar

In conversatia WhatsApp datata 2026-09-12, David sustine pastrarea unei bucle
deterministe pentru rover: SIFTA poate propune obiective, dar nu trebuie sa
inlocuiasca fiecare comanda de servo cu o decizie LLM din cadre succesive.
Aceasta este pozitia lui David din mesajele furnizate, nu rezultatul unei noi
verificari a firmware-ului sau al unei certificari Nav2/SLAM.
Propunerea anterioara cu iPhone/ARKit este o varianta senzoriala separata;
ARKit necesita integrare iOS nativa, nu se presupune disponibil in pagina web.
Videoul este deja primit si documentat mai sus. Pentru adaptor lipsesc contractul
de comunicare si firmware-ul, nu o retransmitere a aceluiasi video.

## Corectia episodului audio Instagram

Proprietarul a explicat explicit ca World STT din captura de ecran de la 18:38
provenea din clipuri Instagram redate pe difuzorul telefonului. Dialogul despre
furt nu era adresat lui Alice. Pastram corectia ca declaratie a proprietarului
despre acel episod; nu atribuim automat toate sunetele viitoare aceleiasi surse.
Aceasta observatie motiveaza jobul de sincronizare si atribuire din handoff.
