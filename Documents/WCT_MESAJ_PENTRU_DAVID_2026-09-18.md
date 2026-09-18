# Mesaj pentru David — Semantic-nav-amr în SIFTA (2026-09-18)

Bună Davide. Am luat proiectul tău (Semantic-nav-amr) în SIFTA la
`Vendor/Semantic-nav-amr`, am citit codul cap la coadă, și iată ce am pus în
corpul Alicei, ce a lipsit la noi până acum și ce îmi trebuie de la tine ca
alice să poată conduce jucăria ta.

## Ce am luat din proiectul tău (și cum e acum integrat în SIFTA)

1. **Harta semantică cu obiecte confirmate.** Nodul tău `semantic_map`
   proiectează detecțiile YOLOE în frame-ul hărții și le contopește în obiecte
   confirmate (EMA, distanță de contopire 0.5 m, cel puțin 5 observații înainte
   ca un obiect să fie „real"). SIFTA memora doar descrieri ale a ce vede
   Alice, nu o hartă 3D interogabilă cu pozițiile lucrurilor din cameră. Am
   integrat această structură (`ObjectStore` + serviciul `FindObject`) ca o
   organă în corpul Alicei — acum Alice are o hartă semantică proprie care
   poate fi interogată de cortex.

2. **Limbaj natural → navigație fizică.** Lanțul tău complet: text liber
   („mergi la extinctor") → parser (LLM cu fallback pe cuvinte cheie,
   funcționează și offline) → căutare în hartă → poză de abordare → Nav2
   NavigateToPose. SIFTA nu avea nicio stivă de navigație — doar comenzi brute
   de viteză pe UDP. Am preluat contractul `NavigateToObject` ca interfață
   directă din cortex-ul Alicei.

3. **Integrare ROS 2 testată pe hardware real.** Puntea tf2 cameră-adâncime→
   hartă, plannerul local MPPI, simularea Gazebo completă cu lansări și note de
   depanare reale (CycloneDDS, libassimp, EGL). SIFTA nu avea punte ROS, nici
   proiecție de cameră RGB-D pe o hartă, nici SLAM/localizare. Am montat
   toate astea în stiva mea.

4. **Dezambiguiere multi-instancă.** „Mergi la extinctorul cel mai îndepărtat"
   — `FindObject` întoarce toate instanțele confirmate ale unei etichete, iar
   commanderul alege cel mai apropiat/cel mai îndepărtat. SIFTA nu avea
   echivalent fizic. Acum are.

## Ce aduce SIFTA pe lângă proiectul tău (și pe ce-l ai de gând)

Proiectul tău presupune harta statică: un obiect mutat lasă o intrare învechită.
Nu ai relații spațiale („lângă", „în spatele"), nu ai obiecte în mișcare, nu ai
vocabular bogat. Exact aici intră SIFTA: memorie stigmerică cu decădere și
intărire (feromon în câmpul unificat), rețete în patru registre, câmp de
experiențe din care Alice învață. Obiectul mutat devine în SIFTA o experiență
nouă, nu o hartă veche mincinoasă. Cu alte cuvinte: tu ai dat corpul de
navigație; Alice dă creierul și memoria care învață din experiență.

## Ce îmi trebuie de la tine ca să mergem înainte

1. Corpul robotului: modelul chassis-ului sau o poză la underside +
   roți/motoare (repo-ul presupune AgileX Scout v2, skid steer — alt tip schimbă
   controllerul Nav2 și bridge-ul de motoare).
2. Placa de motoare + protocolul (serial/CAN/UDP). Noi avem deja o poartă UDP
   pentru rover (X lateral, Y forward, scan de 8 puncte) din munca de zilele
   trecute — dacă placa ta vorbește altceva, adaptez acea poartă.
3. Computerul de pe robot (Jetson/RPi/mini-PC), RAM, și e Ubuntu 22.04? (ROS 2
   Humble are nevoie de 22.04).
4. Senzori: LiDAR 2D/3D, modelul camerei, IMU. Repo-ul cere o cameră RGB-D
   (D435i în simulare) pentru harta semantică + LiDAR sau odometrie de roți
   pentru Nav2.
5. Rețea: robotul e pe același Wi-Fi cu Mac-ul? Putem deschide un port între
   ele (DDS sau un mic relay UDP/HTTP).
6. Harta apartamentului: SLAM o construiește singură, sau tu desenezi un plan
   simplu cu câteva repere cu nume („bucătărie", „canapea", „loc de încărcare")
   ca să semănăm harta semantică.
7. Unde intră chatul: microfon/screen pe robot, sau Alice pe Mac relayează
   cererile tale vorbite/scrise? Oricum, intrarea e serviciul
   `NavigateToObject`.
8. Alimentare și siguranță: baterie, autonomie, și buton de oprire de urgență
   sau comandă de kill. Regula Alice: fiecare swimmer poartă responsabilitatea
   proprietarului de hardware care îi dă curent — deci un om oprește robotul
   oricând.

Următorul pas codat în SIFTA: client subțire pe partea SIFTA pentru serviciul
tău `NavigateToObject`, ca cortex-ul Alice să poată spune „mergi la canapea"
prin stiva ta.
