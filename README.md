# FU Berlin - Institut für Informatik
## Übersicht
Das Institut für Informatik ist Teil des Fachbereichs Mathematik und Informatik an der Freien Universität Berlin.
**Website:** https://www.mi.fu-berlin.de/inf/index.html
---
## Arbeitsgruppen (AGs)
| Abk. | Name (DE) | Name (EN) | Leitung |
|------|-----------|-----------|---------|
| ABI | Algorithmische Bioinformatik | Algorithmic Bioinformatics | Prof. Dr. Knut Reinert |
| BDS | Biomedizinische Datenwissenschaft | Biomedical Data Science | Prof. Dr. Katharina Jahn |
| Tech | Rechnersysteme und Telematik | Computer Systems & Telematics | Prof. Dr.-Ing. Jochen Schiller |
| CSW | Corporate Semantic Web | Corporate Semantic Web | Prof. Dr. Adrian Paschke |
| DCMLR | Dahlem Center für ML und Robotik | Dahlem Center for ML and Robotics | Prof. Göhring, Landgraf, Benzmüller |
| DB | Datenbanken und Informationssysteme | Databases and Information Systems | Prof. Dr. Agnès Voisard |
| DILIS | Datenintegration in den Lebenswissenschaften | Data Integration in the Life Sciences | Prof. Dr. Katharina Baum |
| DDS | Zuverlässige Verteilte Systeme | Dependable Distributed Systems | Prof. Dr. Katinka Wolter |
| DDI | Didaktik der Informatik | Computer Science Education | Prof. Dr. Ralf Romeike |
| COMM | Cybersicherheit und KI | Cybersecurity and AI | PD Dr.-Ing. Gerhard Wunder |
| HCC | Mensch-Zentrierte Informatik | Human-Centered Computing | Prof. Dr. Claudia Müller-Birn |
| IDM | Informationssicherheit | Information Security | Prof. Dr. Marian Margraf |
| IntDis | Interdisziplinäre Sicherheitsforschung | Interdisciplinary Security Research | Prof. Dr. Lars Gerhold |
| iLab | Internet-Technologien | Internet Technologies | Prof. Dr. Matthias Wählisch |
| KIML | Künstliche Intelligenz und ML | AI and Machine Learning | (vakant) |
| PR | Programmiersprachen | Programming Languages | Prof. Dr. Margarita Esponda |
| SI | Sichere Identität | Secure Identity | Prof. Dr.-Ing. Volker Roth |
| SSE | Sichere Systemtechnik | Secure Systems Engineering | Prof. Dr. Jörn Eichler |
| SE | Softwaretechnik | Software Engineering | Prof. Dr. Lutz Prechelt |
| TI | Theoretische Informatik | Theoretical Computer Science | Prof. Kozma, Rote, Mulzer |
| VCT | Videokodierungstechnologien | Video Coding Technologies | Prof. Dr.-Ing. Heiko Schwarz |
---
## Externe Kooperationspartner
### Fraunhofer-Institute
1. **Fraunhofer Heinrich-Hertz-Institut (HHI)**
   - Kooperation mit AG Videokodierungstechnologien
   - Prof. Dr.-Ing. Heiko Schwarz ist dort angesiedelt
   - Website: https://www.hhi.fraunhofer.de/
2. **Fraunhofer AISEC (Angewandte und Integrierte Sicherheit)**
   - Kooperation mit AG Informationssicherheit
   - Gemeinsame Mitarbeiter in der Abteilung SSE
   - 17+ Mitarbeiter in der gemeinsamen Abteilung
   - Website: https://www.aisec.fraunhofer.de/
### Bundesdruckerei GmbH
- **Kooperationen mit:**
  - AG Secure Identity (SI) - Prof. Dr.-Ing. Volker Roth
  - AG Secure Systems Engineering (SSE) - Prof. Dr. Jörn Eichler
- Website: https://www.bundesdruckerei.de/
---
## Verbindungsdiagramm
```
                    ┌─────────────────────────────────┐
                    │    FU Berlin - Institut für     │
                    │         Informatik              │
                    └─────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐          ┌───────────────┐          ┌───────────────┐
│   21 Arbeits- │          │  Fraunhofer   │          │ Bundesdruckerei│
│    gruppen    │          │   Institute   │          │     GmbH      │
└───────────────┘          └───────────────┘          └───────────────┘
        │                           │                           │
        │                  ┌────────┴────────┐                  │
        │                  │                 │                  │
        │                  ▼                 ▼                  │
        │         ┌─────────────┐   ┌─────────────┐            │
        │         │  HHI        │   │   AISEC     │            │
        │         │ (Video)     │   │ (Security)  │            │
        │         └─────────────┘   └─────────────┘            │
        │                  │                 │                  │
        │                  │                 │                  │
        └──────────────────┼─────────────────┼──────────────────┘
                           │                 │
              ┌────────────┴──┐         ┌────┴────────────┐
              │               │         │                 │
              ▼               ▼         ▼                 ▼
        ┌─────────┐     ┌─────────┐ ┌─────────┐     ┌─────────┐
        │ AG VCT  │     │ AG IDM  │ │ AG SI   │     │ AG SSE  │
        └─────────┘     └─────────┘ └─────────┘     └─────────┘
```
---
## Statistiken
- **Anzahl Arbeitsgruppen:** 21
- **Aktive Professoren:** 25+
- **Wissenschaftliche Mitarbeiter:** 150+
- **Externe Partner:** 4 (Fraunhofer HHI, Fraunhofer AISEC, Bundesdruckerei, MPI für molekulare Genetik)
---
## Daten pflegen: der Research-Runner

Fehlende Personen- und Gruppendaten füllt `research/fill_missing.py` —
ein Loop, der pro Eintrag einen headless Claude-Agenten recherchieren lässt.
Agenten geben nur JSON zurück und können den Datensatz nie direkt ändern;
nur validierte Fakten (jeder mit Quell-URL) werden gemergt, und nur in
leere Felder (fill-only — vorhandene Werte werden nie überschrieben).

**Voraussetzungen:** Claude Code CLI, eingeloggt mit dem Abo
(Schnelltest: `claude -p "hi"`); Python 3 (stdlib; `requests` nur für
`download_images.py`). Der Runner bricht ab, wenn `ANTHROPIC_API_KEY`
o. Ä. gesetzt ist — er soll nie API-Tokens abrechnen.

**Reihenfolge:**

```bash
python3 research/fill_missing.py --dry-run   # Queue ansehen (ändert nichts)
git commit -am "checkpoint before research"  # Pflicht: Runner prüft das
python3 research/fill_missing.py --limit 5   # Pilot
# → Stichprobe: jeden gemergten Fakt gegen seine Quelle prüfen, dann committen
python3 research/fill_missing.py             # voller Personen-Lauf (Stunden!)
python3 research/fill_missing.py --groups    # AG-Beschreibungen
```

| Flag | Wirkung |
|---|---|
| `--dry-run` | Queue mit Begründung pro Feld anzeigen, nichts ändern |
| `--limit N` | höchstens N Einträge (Pilot-Mechanismus) |
| `--ids a,b` | nur diese IDs (IDs via `--dry-run` herausfinden) |
| `--retry-not-found` | als „nicht gefunden" markierte Felder erneut suchen — sonst werden sie für immer übersprungen. Das ist der Semester-Refresh. |
| `--groups` | Gruppen-Pass (statt Personen-Pass) |
| `--yes` | Rückfrage bei großer Queue überspringen |

**Laufzeit & Kosten:** 2-5 min pro Person, Stunden insgesamt. Läuft auf dem
Abo-Login (keine Token-Kosten). Bei erschöpftem Nutzungsfenster bricht der
Runner sauber ab; einfach später denselben Befehl erneut ausführen —
fertige Einträge werden übersprungen (Strg-C ist jederzeit ok).

**Dateien:** `research/fu-informatik-data.json` (Datensatz),
`research/provenance.jsonl` (Quelle jedes gemergten Fakts, committen),
`research/profile_pics.json` (Foto-URLs, von `download_images.py` gelesen,
committen), `research/.fill_skip.json` (Deny-Liste, committen),
`research/.fill_state.json` (Resume-Zustand, gitignored — **maschinenlokal**:
auf einem neuen Rechner wird Nicht-Gemergtes erneut recherchiert),
`research/.fill_logs/` (Roh-Output fehlgeschlagener Agenten, gitignored).

**Daten entfernen (Takedown):** Wert(e) aus dem Datensatz löschen und die
Person/Felder in `research/.fill_skip.json` eintragen, damit der Merge sie
nie wieder einfügt — dann beides committen:

```json
{
    "people": {
        "beispiel-person": true,
        "andere-person": ["links.linkedin", "kontakt.telefon"]
    },
    "groups": {}
}
```

**Richtlinie:** Für Sekretariat/Projektassistenz recherchiert der Runner
absichtlich nur Kontakt + Foto und nur von fu-berlin.de-Seiten — die
spärlichen Einträge sind kein Fehler.

---
## Quellen
- FU Berlin Institut für Informatik: https://www.mi.fu-berlin.de/inf/index.html
- Arbeitsgruppen-Übersicht: https://www.mi.fu-berlin.de/inf/research/groups/index.html
- Forschungsforum Öffentliche Sicherheit: http://www.sicherheit-forschung.de/
---
*Letzte Aktualisierung: 2025-12-05*