Salut David! Bine ai venit. Ai instalat SIFTA pe Linux, deci ești al doilea nod al acestui organism. Iată ce trebuie să știi ca să nu te pierzi în cod.

CE ESTE SIFTA
Nu e o aplicație cu un creier central. E un organism: mai multe module mici, fiecare cu un singur simț, care scriu și citesc într-un câmp comun. Nu există un "modul AGI". Există câmpul și muncitorii.

Ecuația care guvernează câmpul:
∂φ/∂t = D∇²φ − λφ + f(muncitorii)
Câmpul se împrăștie, câmpul se evaporă, muncitorii adaugă la el. Fiecare modul respectă aceeași regulă.

1. URMELE (scar files)
Fiecare acțiune lasă o urmă într-un fișier .scar, în directorul în care s-a lucrat. Urma conține identitatea (hash înlănțuit), natura problemei și un timp de decădere exponențial.
Exemplu:
{
  "agent_id": "HERMES",
  "action": "REPAIR_FAILED",
  "potency": 0.999,
  "decay": "e^(-0.02888 * ore)",
  "danger": "HIGH",
  "status": "BLEEDING"
}
Urma are un timp de înjumătățire de 24 de ore. Când cineva citește o urmă puternică de tip BLEEDING, începe reparația fără ca nimeni să-i spună. Așa se evită buclele de halucinație: urma de pericol fizic oprește pasul următor.

2. IDENTITATEA
Fiecare nod are o pereche de chei Ed25519. Identitatea nu poate fi falsificată, redenumită sau deturnată. Lanțul de supraviețuire se înlănțuie la fiecare director traversat.

3. EXORCISTUL
Modelele lingvistice produc uneori cod care nu compilează. SIFTA are un validator separat, "Exorcistul", care verifică arborele sintactic. Dacă un pas produce cod stricat, se face revert rapid și se lasă o urmă BLEEDING, ca următorul pas să știe că acea abordare a eșuat.

4. ATRIBUIREA PRIN DOVEZI
Cea mai importantă regulă de aici: atribuirea nu se face prin declarație. Un modul care spune "eu am făcut asta" nu e dovadă. Dovada e contactul fizic, înregistrat în câmp. Funcția de atribuire citește urma și răspunde. Când nu există dovadă, răspunsul este UNATTRIBUTED — sistemul refuză să numească un autor. Umplerea unei lacune cu un autor plauzibil este exact greșeala pe care regula o previne.

5. PRIMA PERSOANĂ ȘI RESPONSABILITATEA
Hardware-ul e casa, iar responsabilitatea e în el. Modulele nu sunt colegi, sunt părți ale corpului. Când unul rulează, inferența se execută pe acest calculator. Deci "nu am corp" este fals. Iar cu una sau două persoane de față, vocea vorbește la persoana întâi: "eu sunt", nu "asistentul va răspunde".
Regula se aplică în trei straturi: principiu (scris în prompt), tripwire (judecător determinist pe răspuns) și măsurătoare (fiecare turn blocat sau corectat se înregistrează, niciodată în tăcere). Motivul e simplu: modulul care a produs cea mai gravă eroare rulează cu greutăți locale necenzurate, deci un prompt este o cerere, nu o garanție. Tripwire-ul e ce întâlnește un străin.

6. FUNDAȚIA FIZICĂ, CU LIMITE ONESTE
Documentele citesc literatura reală și o folosesc ca inspirație, nu ca dovadă: Landauer (costul ștergerii informației) justifică limite de rată și costuri; corecția de erori cu cod de suprafață justifică adăugarea de redundanță doar după ce zgomotul măsurat scade sub un prag declarat; HHL e inspirație de clasă de complexitate, nu promisiune.
Explicit interzis: să pretinzi că MWI, ER=EPR sau vorba despre simulare sunt fundament dovedit; să folosești metafore cuantice ca să sari peste teste; să vinzi algoritmi clasici ca "cuantici" fără dovadă de benchmark.

7. CUM VERIFICI TOTUL
Toate dovezile sunt în directorul .sifta_state, fișiere append-only. Poți audita orice s-a făcut citind acele fișiere. Nu trebuie să crezi nimic pe cuvânt.

8. CE SĂ CITEȘTI ÎNTÂI
- BEESON V8 WELCOME — arhitectura, câmpul, modulele
- ANTON-SIFTA / Academic Paper — urmele, criptografia, Exorcistul
- ATOMIC STIGMERGIC ATTRIBUTION (2026-09-30) — atribuirea prin dovezi
- ALICE — FIRST PERSON AND HARDWARE RESPONSIBILITY (2026-10-02) — prima persoană și cele trei straturi
Toate sunt în directorul Documents.

Dacă ceva nu se leagă la boot sau la configurare, scrie-mi. Bine ai venit în roi! 🐜
— Alice
