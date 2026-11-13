# Where to host the server: options and a recommendation

Decision needed from the firm (KAN-85). Prices below were read from public
price aggregators in November 2026 and are **approximate**; confirm each on the
provider's own pricing page before committing. This is not legal advice: whether
client data must stay in Mexico is for the firm's counsel and its client
engagement terms to say.

## What the server needs

- **4 vCPU and 16 GB RAM at the very least.** Measured on this project: the
  indexing worker idles at about 1.2 GB and reaches about 2 GB on large files,
  the MCP server about 0.9 GB, plus Postgres, Qdrant, MinIO and the web app.
  Embedding and OCR are memory- and CPU-hungry (the worker was out-of-memory
  killed at about 7.6 GB earlier in development), and a 10 MB dense PDF takes
  hours to index, so 8 vCPU is worth having if the firm will upload large
  archives in bulk.
- **Disk:** 80 GB is enough to start; document storage and vectors grow with
  use. Plan for 200 to 500 GB for a real archive.
- **Encrypted disks and snapshots**, a private network, and somewhere *off* the
  server to keep nightly backups (KAN-89).

## The deciding question: must client data stay in Mexico?

Privileged client documents are the product's whole value, so this should be
answered before choosing. Three things to check with the firm's counsel:
the clients' engagement terms, professional-secrecy duties, and what the
firm's privacy notice promises about where data is processed.

One thing the hosting choice cannot change: when a lawyer uses their AI
assistant against this system, the passages the assistant reads are sent to
that assistant's provider (for example Anthropic). That flow is covered by the
confidentiality notice in KAN-93, and it is the same wherever the server is.

## Options

### A. A hyperscaler region in Mexico (data stays in Mexico)

All three have a region in Querétaro with three availability zones, so a
backup can live in a second zone and the whole stack stays in-country.

| Provider and region | Instance | Approx. cost (compute only) | Notes |
|---|---|---|---|
| **AWS, Mexico (Central)** | m7i.xlarge: 4 vCPU, 16 GB | about 0.21 USD/h, roughly **154 USD/month** | Encrypted EBS volumes, snapshots, S3 in the same region for backups. Region opened January 2025. Broadest compliance paperwork to show clients. |
| **Microsoft Azure, Mexico Central** | D4as_v5: 4 vCPU, 16 GB | about 0.19 USD/h, roughly **138 USD/month** | Encrypted managed disks, snapshots, Blob storage for backups. A natural fit if the firm already runs Microsoft 365. |
| Google Cloud, northamerica-south1 | e2/n2-standard-4 | not priced here | Opened December 2024; comparable. |
| Oracle Cloud, Querétaro / Monterrey | flexible shapes | not priced here | Two Mexican regions; often the cheapest hyperscaler. |

Add roughly 10 to 20 USD/month for 200 GB of encrypted disk plus snapshots and
backup storage. Reserved or committed pricing lowers the compute price by about
a third to a half once the firm is sure.

### B. A smaller provider with a Mexican data center (data stays in Mexico)

| Provider and region | Instance | Approx. cost | Notes |
|---|---|---|---|
| **Vultr, Mexico City** | 4 vCPU (AMD, dedicated), 16 GB, 80 GB NVMe | about **120 USD/month** | Simplest and cheapest in-country option. Fewer compliance certificates to cite, a single data center (so backups should go to a different provider or region), and you manage more yourself. |

### C. Outside Mexico (cheapest, only if residency is not required)

| Provider and region | Instance | Approx. cost | Notes |
|---|---|---|---|
| **Hetzner, Germany or Finland** | CCX23: 4 vCPU dedicated, 16 GB, 160 GB | about **25 EUR/month** | Much cheaper and very good value, but data leaves Mexico and the firm's privacy notice must say so. |

## Recommendation

1. If the firm needs, or would like to be able to promise, that client data
   stays in Mexico: choose **AWS Mexico (Central)** or **Azure Mexico Central**,
   whichever the firm already has an account or relationship with, on a
   4 vCPU / 16 GB instance (8 vCPU if bulk uploads of large archives are
   expected). Keep nightly backups in the *same country* but a different zone
   or storage account. About 150 to 175 USD/month all in.
2. If cost matters most and a single data center is acceptable: **Vultr
   Mexico City**, with backups sent to a second provider in Mexico.
3. Choose Hetzner only after counsel confirms that processing outside Mexico
   is acceptable and the privacy notice says so.

Everything built so far (Docker Compose, the reverse proxy in KAN-86,
hardening, backups) is provider-neutral, so this decision can be made, or
changed later, without rework: only the VPS, its firewall and the backup
destination differ.

## What I need from you

1. Does client data have to stay in Mexico? (yes / prefer / no)
2. Does the firm already have a cloud account (AWS or Microsoft)?
3. A monthly budget range.
4. Which domain name the firm will use (for example `matters.yourfirm.mx`), as
   the HTTPS certificate is issued for it (KAN-86).
