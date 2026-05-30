# UC Irvine Libraries PDF-to-HTML Accessibility Converter

A lightweight Streamlit frontend for the existing AWS PDF-to-HTML accessibility pipeline.

## Workflow

```text
Streamlit Community Cloud
→ private S3 uploads/<unique-id>.pdf
→ existing Pdf2HtmlPipeline Lambda
→ private S3 remediated/<unique-id>.html
→ Download HTML File
```

## Files to upload to GitHub

```text
app.py
requirements.txt
README.md
secrets.toml.example
.gitignore
assets/
iam/
```

The public GitHub repo should not contain real credentials.

## Deploy on Streamlit Community Cloud

1. Create a GitHub repository.
2. Upload the files in this package.
3. In Streamlit Community Cloud, create an app from the repo.
4. Use `app.py` as the main file.
5. Open the app's **Settings → Secrets** page.
6. Copy the contents of `secrets.toml.example`.
7. Paste them into Streamlit Secrets.
8. Replace the blank values with your real shared-key hash and restricted IAM credentials.
9. Deploy.

## Run locally after cloning

Streamlit reads local secrets from:

```text
.streamlit/secrets.toml
```

After cloning the repo, create the hidden `.streamlit` folder and copy the public template into the correct location:

```bash
mkdir -p .streamlit
cp secrets.toml.example .streamlit/secrets.toml
```

Then open:

```text
.streamlit/secrets.toml
```

and fill in your private values.

Install dependencies and run the app:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Do not commit `.streamlit/secrets.toml`. It is listed in `.gitignore`.

## Generate the shared access-key hash

Use AWS CloudShell:

```bash
ACCESS_KEY=$(openssl rand -base64 24)
echo "PRIVATE ACCESS KEY TO SHARE:"
echo "$ACCESS_KEY"
echo
echo "HASH TO STORE IN STREAMLIT:"
printf '%s' "$ACCESS_KEY" | sha256sum | awk '{print $1}'
```

Store the hash in:

```toml
APP_ACCESS_KEY_SHA256 = "PASTE_HASH_HERE"
```

Share the private access key only with approved testers.

## Restricted IAM policy

Use:

```text
iam/streamlit_s3_policy.json
```

The included policy grants only:

- `s3:PutObject` to `uploads/*`
- `s3:GetObject` to `remediated/*`
- `s3:ListBucket` limited to the `remediated/*` prefix

The `s3:ListBucket` permission is required while polling for an output that may not exist yet.

## Prototype notice

Use non-sensitive test PDFs during Streamlit Community Cloud testing. The generated HTML is AI-assisted output and should be reviewed before publication.
