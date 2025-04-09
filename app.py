import sys
import streamlit as st # Keep this import too
import os
import google.generativeai as genai
from PyPDF2 import PdfReader
import io # Needed for reading file uploader bytes with PyPDF2

# --- Configure Google Generative AI Client ---
try:
    # Get API key from Streamlit secrets
    api_key = st.secrets["google_api_key"]
    # --- Initialize the API ---
    genai.configure(api_key=api_key)
    # --- Define Model Name ---
    model_name = "gemini-2.5-pro-latest"

except KeyError:
    st.error("Fejl: Google API-nøgle ikke fundet i Streamlit secrets (google_api_key). Tilføj den venligst.")
    st.stop() # Stop execution if API key is missing
except Exception as e:
    st.error(f"Fejl under konfiguration af Google AI Client: {e}")
    st.stop()


# --- UI Text (Danish) ---
st.markdown("""
# 📝 AI-drevet Ansøgningsgenerator

Generer en skræddersyet ansøgning. Alt du skal gøre er:
1. Upload dit CV eller kopier/indsæt dit CV/dine erfaringer
2. Indsæt en relevant jobbeskrivelse
3. Indtast andre relevante bruger-/jobdata
"""
)

# --- Resume Input ---
# Initialize res_text to avoid potential errors if form submitted without interaction
res_text = ""

res_format = st.radio(
    "Vil du uploade eller indsætte dit CV/dine nøgleerfaringer?",
    ('Upload', 'Indsæt'),
    key='resume_format_radio' # Added a key for potential state issues
)

if res_format == 'Upload':
    res_file = st.file_uploader('📁 Upload dit CV i PDF-format', type='pdf')
    if res_file is not None:
        try:
            # PyPDF2 needs a file-like object, io.BytesIO works well here
            pdf_bytes = io.BytesIO(res_file.getvalue())
            pdf_reader = PdfReader(pdf_bytes)

            # Collect text from pdf
            extracted_text = ""
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text: # Check if text extraction was successful
                     extracted_text += page_text + "\n" # Add newline between pages
            res_text = extracted_text
            if not res_text:
                 st.warning("Kunne ikke udtrække tekst fra PDF'en. Prøv venligst at indsætte teksten manuelt.")

        except Exception as e:
            st.error(f"Fejl ved læsning af PDF-fil: {e}")
            st.warning("Prøv venligst at indsætte teksten manuelt.")
            # Ensure res_text is cleared if upload fails after selection
            res_text = ""
else:
    res_text = st.text_area('Indsæt CV-elementer eller relevant erfaring her', height=200) # Use text_area for better pasting experience

# --- Input Form ---
with st.form('input_form'):
    # other inputs
    job_desc = st.text_area('Indsæt jobbeskrivelsen her', height=200) # Use text_area
    user_name = st.text_input('Dit navn')
    company = st.text_input('Virksomhedens navn')
    manager = st.text_input('Ansættende leder (valgfrit, lad stå tomt hvis ukendt)')
    role = st.text_input('Jobtitel/Stilling ansøgt')
    referral = st.text_input('Hvordan hørte du om denne mulighed?')
    # Gemini uses temperature in its generation_config
    ai_temp = st.slider('AI Temperatur (Kreativitet: 0.0 = Meget faktuel, 1.0 = Meget kreativ)', 0.0, 1.0, 0.7) # Changed to slider

    # submit button
    submitted = st.form_submit_button("Generer Ansøgning")

# --- Generation Logic ---
if submitted:
    # Basic input validation
    if not res_text:
        st.error("Angiv venligst CV/erfaringstekst (enten via upload eller indsætning).")
    elif not job_desc:
        st.error("Indsæt venligst jobbeskrivelsen.")
    elif not user_name:
        st.error("Indtast venligst dit navn.")
    elif not company:
        st.error("Indtast venligst virksomhedens navn.")
    elif not role:
        st.error("Indtast venligst jobtitel/stilling.")
    else:
        with st.spinner(f"Genererer ansøgning med {model_name}... Vent venligst."): # Updated spinner text
            try:
                # --- Construct the Prompt for Gemini ---
                # Prompt remains the same as before
                prompt = f"""
                Opgave: Skriv et udkast til en professionel ansøgning på dansk.

                Baser ansøgningen på følgende information:

                1.  **Ansøgers CV/Erfaring:**
                    ```
                    {res_text}
                    ```

                2.  **Jobbeskrivelse for den søgte stilling:**
                    ```
                    {job_desc}
                    ```

                3.  **Detaljer:**
                    *   Ansøgers Navn: {user_name}
                    *   Virksomhed: {company}
                    *   Stilling: {role}
                    *   Ansættende Leder: {manager if manager else "Ukendt"}
                    *   Hvor stillingen blev fundet: {referral if referral else "Ikke specificeret"}

                **Instruktioner for ansøgningens struktur og indhold:**

                *   **Sprog:** Dansk. Tonen skal være professionel, entusiastisk og skræddersyet til stillingen.
                *   **Afsender:** Brug {user_name} som afsender.
                *   **Modtager:** Hvis en ansættende leder ({manager}) er angivet og ikke er "Ukendt", adresser brevet til vedkommende (f.eks. "Kære [Managers Navn]"). Ellers brug en generel hilsen som "Vedrørende stillingen som {role}" eller adresser til HR-afdelingen, hvis det virker passende.
                *   **Alinea 1 (Introduktion):**
                    *   Præsenter dig selv ({user_name}).
                    *   Angiv klart den stilling ({role}), du søger.
                    *   Nævn, hvor du så stillingsopslaget ({referral}), hvis angivet.
                    *   Giv en kort opsummering af din mest relevante profil/kernekompetence i forhold til stillingen, baseret på CV'et.
                *   **Alinea 2 (Motivation og Match):**
                    *   Uddyb, hvorfor du er en god kandidat.
                    *   TRÆK DIREKTE PARALLELLER mellem specifikke erfaringer/kvalifikationer fra CV'et ({res_text}) og de krav/ønsker, der er nævnt i jobbeskrivelsen ({job_desc}). Vær konkret.
                    *   Vis din motivation for netop denne stilling og virksomhed ({company}).
                *   **Alinea 3 (Afslutning):**
                    *   Gentag din interesse for stillingen og virksomheden.
                    *   Opsummer kort, hvad du kan tilbyde.
                    *   Udtryk ønske om en samtale for at uddybe din ansøgning.
                    *   Tak for modtagerens tid og overvejelse.
                *   **Afsluttende Hilsen:** Brug en passende professionel hilsen (f.eks. "Med venlig hilsen") efterfulgt af dit navn ({user_name}).
                *   **Kontaktinformation:** Inkludér *ikke* detaljeret kontaktinformation (som adresse, email, telefon) direkte i brødteksten, da dette typisk står i CV'et eller brevhovedet. Fokuser på selve ansøgningsteksten. Sørg dog for at brevet afsluttes med afsenderens navn.
                *   **Formatering:** Sørg for passende linjeskift og luft mellem afsnittene for god læsbarhed.

                Generer nu ansøgningsteksten baseret på ovenstående.
                """

                # --- Define Generation Configuration ---
                generation_config = {
                    "temperature": ai_temp
                }

                # --- Call Gemini API using the standard method ---
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(
                    prompt,
                    generation_config=generation_config
                )

                # --- Display Response ---
                if hasattr(response, "text"):
                    response_out = response.text
                else:
                    try:
                        response_out = response.parts[0].text
                    except (AttributeError, IndexError):
                        st.error("Kunne ikke udtrække tekst fra API-svaret. Svarstruktur kan have ændret sig.")
                        st.write("Rå API Svar:", response) # Print raw response for debugging
                        response_out = "" # Prevent further errors

                if response_out:
                    st.subheader("Genereret Ansøgning:") # Danish subheader
                    st.markdown(response_out) # Use markdown for potentially better formatting

                    # --- Download Button ---
                    st.download_button(
                        label="Download Ansøgningen (.txt)", # Danish label
                        data=response_out.encode('utf-8'), # Encode as UTF-8 for broad compatibility
                        file_name=f"ansoegning_{user_name.replace(' ', '_')}_{company.replace(' ', '_')}.txt",
                        mime='text/plain'
                    )
                # else: error handled above

            except genai.types.generation_types.BlockedPromptException as bpe:
                 st.error(f"Kunne ikke generere ansøgning. Prompten blev blokeret af sikkerhedsfiltre. Prøv at omformulere input. Detaljer: {bpe}")
            except Exception as e:
                st.error(f"Der opstod en fejl under generering af ansøgningen: {e}")
                # Consider logging the full error for debugging
                # st.exception(e)