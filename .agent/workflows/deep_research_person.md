---
description: Perform deep research on a person to gather comprehensive details (CV, contact, links, image) and update the JSON database.
variables:
  - name: person_name
    description: Name of the person to research (e.g. "Prof. Dr. Claudia Müller-Birn")
  - name: person_id
    description: The ID of the person in fu-informatik-data.json (e.g. "mueller-birn-claudia")
---

1. **Initial Search**: Perform web searches to find the person's digital footprint.
   - Tool: `search_web`
   - Queries:
     - `FU Berlin ${person_name} contact room phone`
     - `${person_name} cv curriculum vitae`
     - `${person_name} publications google scholar dblp`
     - `${person_name} linkedin github`
     - `${person_name} website`

2. **Deep Scrape (Browser)**: Visit the most relevant pages (FU Profile, Personal Website, CV PDF if accessible as HTML view) to extract specific details.
   - Tool: `browser_subagent`
   - Task: "Extract the following details for ${person_name}:
     1. **Profile Image URL**: High resolution if possible.
     2. **Contact**: Email, Phone, Office Address (Street + Room number).
     3. **Links**: Gather URLs for: Personal Website, GitHub, LinkedIn, Google Scholar, ResearchGate, DBLP, Xing, Mastodon/Twitter, Wikipedia.
     4. **CV/Vita**: Look for a 'Vita', 'CV', or 'About' section. Extract key dates:
        - Born (Year/Location)
        - Education (Bachelor, Master, PhD - University & Year)
        - Career (Positions, Companies/Universities, Start-End Dates)
        - Start date at FU Berlin.
     5. **Research**: Find a link to their full publications list. Identify 3-5 keywords or research interests."

3. **Update Image Script**: If a profile image URL was found:
   - Tool: `replace_file_content`
   - Target: `download_images.py`
   - Action: Add the person's ID and URL to the `PROFILE_PICS` dictionary.
   - Tool: `run_command`
   - Command: `python download_images.py`
   - Note: This will download the image to `research/images/` and update the JSON `profilbild` path automatically.

4. **Update JSON Data**: Use the research results to update the person's entry in `research/fu-informatik-data.json`.
   - Tool: `read_json` (or `view_file` to read `research/fu-informatik-data.json`)
   - Tool: `replace_file_content`
   - Target: `research/fu-informatik-data.json`
   - Instructions: Find the object with `id: "${person_id}"`. Update/Add fields:
     - `kontakt`: { `email`, `telefon`, `ort` (Address), `raum` }
     - `links`: { `website`, `github`, `linkedin`, `google-scholar`, `orcid`, `dblp`, `cv-pdf` (if applicable) }
     - `vita`: { `positionen`: [Array of strings, e.g. "2010: PhD at TU Berlin", "since 2015: Professor at FU Berlin"] }
     - `forschung`: { `interessen`: [Array of keywords], `publikationen`: "URL to publications" }
     - `auszeichnungen`: [Array of {name, jahr}] if found.

5. **Verification**: Verify the data is correctly structured and Valid JSON.
