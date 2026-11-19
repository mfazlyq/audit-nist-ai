# Security and data-handling notes

## API credentials

- Supply the Groq API key through the environment or Streamlit secrets.
- Do not hard-code credentials in Python source files.
- Do not commit .env, .streamlit/secrets.toml, or real API keys.
- Rotate a credential immediately if it is accidentally exposed.

## Uploaded documents

The prototype extracts text from uploaded PDFs and places retrieved passages in prompts sent to the configured Groq model endpoint. Before using institutional material:

1. Confirm you have permission to process and disclose the documents to the selected provider.
2. Remove personal, confidential, classified, or otherwise restricted content unless its processing is explicitly authorized.
3. Review the provider's current data-handling terms and your institution's policies.
4. Prefer synthetic or sanitized documents for development and demonstrations.

## Generated assessments

- Treat model-generated findings as recommendations for human review.
- Verify each control identifier and conclusion against the source document.
- Do not use generated rankings as a formal risk score without a documented, validated scoring method.
- Keep the original documents and the final approved audit evidence under the institution's normal records-management controls.

## Prototype limitations

This repository does not currently implement a full access-control model, an enterprise document-retention workflow, or evidence-level traceability for every finding. Do not treat it as a production audit platform without a separate security and quality review.
