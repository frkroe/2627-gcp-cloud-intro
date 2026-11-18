# Lab 5 – SLAs, costs and responsibilities

**Goal:** put numbers on the decisions of the last two days. How available is our shop? What does it cost in the cloud vs on-prem? Who is responsible for what?

Work in pairs. No cloud resources are created in this lab.

## 5.1 How available is our shop?

An **SLA** (Service Level Agreement) is Google's promise for one service, e.g. “Pub/Sub is available 99.95 % of each month”. If they miss it, you get a credit on your bill, not your lost sales back.

Our shop needs **all** its pieces at the same time, so their availabilities **multiply**:

```bash
python3 scripts/availability.py
```

Answer:

1. How many minutes per month may the Project Setup architecture (scenario A) be down, according to the SLAs?
2. Which single change improves availability the most in scenario B?
3. Add a **scenario C** at the bottom of `scripts/availability.py`: two **independent** single delivery VMs in parallel (uncomment the TODO). Is it better or worse than the MIG?
4. Our own code has bugs too, and the SLA doesn't cover them. What else can take the shop down?


| Availability             | Downtime per month |
| -------------------------- | -------------------- |
| 99 %                     | ≈ 7 h 18 min      |
| 99.9 % (“three nines”) | ≈ 44 min          |
| 99.95 %                  | ≈ 22 min          |
| 99.99 % (“four nines”) | ≈ 4 min           |

## 5.2 CAPEX vs OPEX: what does the shop cost?

**CAPEX** (capital expenditure): money spent up front on things you own, like servers. **OPEX** (operational expenditure): recurring costs, like a monthly cloud bill.

Use the **Google Cloud Pricing Calculator** ([https://cloud.google.com/products/calculator](https://cloud.google.com/products/calculator)), region `europe-southwest1`:


|                        | Option A – Cloud, VMs (Project Setup)      | Option B – Cloud, serverless (Day 2)                                                    | Option C – On-prem                                                    |
| ------------------------ | --------------------------------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------ |
| What                   | 2 × e2-micro running 24/7, 2 × 10 GB disk | Cloud Run: 1 M requests/month · function: 100 k invocations of 12 s · Pub/Sub: < 10 GB | 2 servers in your own room                                             |
| Up-front cost          | 0                                           | 0                                                                                        | 2 × €3,000 (servers)                                                 |
| Monthly cost           | _______                                     | _______                                                                                  | €100 power, cooling & space+ 10 % of an administrator (€45,000/year) |
| **Total over 3 years** | _______                                     | _______                                                                                  | _______                                                                |

Questions:

1. Which option is cheapest for our tiny shop? By how much?
2. When does on-prem become competitive? Think of a big company with **stable, predictable, 24/7** load.
3. What's missing from the on-prem column? Compare it with your list from Lab 1.6.
4. What's the **financial risk** of each option if the shop fails after 6 months?

## 5.3 Your real bill

Open **Billing → Reports**. Filter on your project, then:

- group by **Service**: how much did Compute Engine, Cloud Run and Cloud Build cost these two days?
- group by **Label → app** (the labels from Project Setup): which application cost the most?

Costs appear with a delay of several hours. Check again tomorrow.

## 5.4 Shared responsibility

Moving to the cloud doesn't make security “Google's problem”: the work is **shared**. Fill in **G** (Google), **You**, or **Both**:


| Responsibility                               | VM (Compute Engine) | Cloud Run / functions | Pub/Sub | Gmail (SaaS) |
| ---------------------------------------------- | --------------------- | ----------------------- | --------- | -------------- |
| Physical security of the data centre         |                     |                       |         |              |
| Hardware failures                            |                     |                       |         |              |
| Operating system patches                     |                     |                       |         |              |
| Runtime (Python, Docker) updates             |                     |                       |         |              |
| Application code and its bugs                |                     |                       |         |              |
| Network access (who can reach it)            |                     |                       |         |              |
| IAM: who can do what                         |                     |                       |         |              |
| The data itself (correctness, backups, GDPR) |                     |                       |         |              |

Console check: for every row you marked **You** or **Both**, find the page where *you* control it.

- **VPC network → Firewall:** who may reach your VMs over the network.
- **Cloud Run → orders-api → Security:** *Require authentication* is the Cloud Run version of a firewall rule.
- **IAM & Admin → IAM:** who can do what in your project, including `$SA_DEFAULT`.
- **Compute Engine → VM instances → a MIG VM → Details:** the OS image (Debian 12). Nobody patches it unless you do.

Is there any page where you can choose the operating system of `orders-api`?

Which rows are **always yours**, whatever the service model?

## Final cleanup

Delete **everything** you created in Cloud Intro, as at the end of Project Setup. `catch-up.sh` recreates the basics whenever you need them again.


| Created in                        | Resource                                                                                                                      |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Lab 2.0 (`catch-up.sh`)           | topics `order-events`, `delivery-events` and their subscriptions `-sub`; repository `ecommerce` with the `delivery-app` image |
| Lab 2.2, 4.4                      | Cloud Run service `orders-api` in Madrid and Tokyo                                                                            |
| Lab 2.3                           | function `delivery-function`, subscription `delivery-function-sub`                                                            |
| Lab 4                             | instance group `delivery-mig`, template `delivery-app-tpl`                                                                    |
| Created by Google for your builds | repositories `cloud-run-source-deploy` (Madrid, Tokyo) and `gcf-artifacts`; five buckets with your source code                |

```bash
source config.env

# compute
gcloud compute instance-groups managed delete delivery-mig --region="$REGION" --quiet
gcloud compute instance-templates delete delivery-app-tpl --region="$REGION" --quiet
gcloud compute instances delete delivery-app --zone="$ZONE" --quiet        # only if you still have the Lab 3 VM

# serverless
gcloud functions delete delivery-function --region="$REGION" --quiet
gcloud run services delete orders-api --region="$REGION" --quiet
gcloud run services delete orders-api --region="$FAR_REGION" --quiet

# Pub/Sub
gcloud pubsub subscriptions delete delivery-function-sub order-events-sub delivery-events-sub
gcloud pubsub topics delete order-events delivery-events

# images
gcloud artifacts repositories delete "$AR_REPO" --location="$REGION" --quiet
gcloud artifacts repositories delete cloud-run-source-deploy --location="$REGION" --quiet
gcloud artifacts repositories delete cloud-run-source-deploy --location="$FAR_REGION" --quiet
gcloud artifacts repositories delete gcf-artifacts --location="$REGION" --quiet

# source code uploaded for the builds
gcloud storage rm --recursive \
  "gs://${PROJECT_ID}_cloudbuild" \
  "gs://run-sources-${PROJECT_ID}-${REGION}" \
  "gs://run-sources-${PROJECT_ID}-${FAR_REGION}" \
  "gs://gcf-v2-sources-${PROJECT_NUMBER}-${REGION}" \
  "gs://gcf-v2-uploads-${PROJECT_NUMBER}.${REGION}.cloudfunctions.appspot.com"
```

A `NOT_FOUND` error means that resource is already gone: carry on with the next command.

Check that everything is empty:

```bash
gcloud compute instances list
gcloud compute instance-templates list
gcloud run services list
gcloud functions list
gcloud pubsub topics list
gcloud pubsub subscriptions list
gcloud artifacts repositories list
gcloud storage buckets list
```

Console check: open **Compute Engine** (VM instances, Instance groups, Instance templates), **Cloud Run**, **Pub/Sub** (Topics, Subscriptions), **Artifact Registry** and **Cloud Storage → Buckets**. Every list should be empty.

**Keep** the project with its labels and APIs, your `config.env` and the `edem-dev` configuration.
