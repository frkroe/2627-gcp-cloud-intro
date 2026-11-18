# Lab 2 – One app, three service models

**Goal:** run parts of the shop in the cloud in three different ways, and notice what **you** had to manage each time.


| Model                                   | What Google gives you                                | Our example                                |
| ----------------------------------------- | ------------------------------------------------------ | -------------------------------------------- |
| **IaaS** – Infrastructure as a Service | A virtual machine. Everything inside it is your job. | `delivery-app` on Compute Engine           |
| **PaaS** – Platform as a Service       | A platform that runs your code (here, a container).  | `orders-api` on Cloud Run                  |
| **FaaS** – Function as a Service       | Runs one function each time an event happens.        | `delivery-function` on Cloud Run functions |
| **SaaS** – Software as a Service       | A finished application you just use.                 | Gmail, GitHub, Looker Studio…             |

```bash
cd 2627-gcp-cloud-intro
source config.env
gcloud config set project "$PROJECT_ID"
echo $SA_DEFAULT      # <number>-compute@developer.gserviceaccount.com; if it starts with "-compute", fill in PROJECT_NUMBER

gcloud services enable run.googleapis.com cloudfunctions.googleapis.com \
  cloudbuild.googleapis.com
```

## 2.0 Recreate what you deleted after Project Setup

At the end of Project Setup you deleted everything. This script recreates what we need today: the two Pub/Sub topics with their subscriptions, the `ecommerce` repository and the `delivery-app:v1` image. Google builds the image for you (Cloud Build), so Docker doesn't need to be running.

```bash
./scripts/catch-up.sh       # 3-5 minutes
```

Console check: **Pub/Sub → Topics** shows `order-events` and `delivery-events`, and **Artifact Registry → ecommerce** shows the `delivery-app` image with tag `v1`.

As in Project Setup Lab 4, every app runs as the **default compute service account** (`$SA_DEFAULT`): with the Editor role you can create service accounts, but you can't give them any roles.

## 2.1 IaaS: the delivery app on a virtual machine

Exactly as in Project Setup (Lab 4.3):

```bash
gcloud compute instances create delivery-app \
  --zone="$ZONE" \
  --machine-type=e2-micro \
  --image-family=debian-12 --image-project=debian-cloud \
  --boot-disk-size=10GB \
  --service-account="$SA_DEFAULT" \
  --scopes=cloud-platform \
  --labels="${LABELS},app=delivery" \
  --metadata="app-image=$REGISTRY/delivery-app:v1" \
  --metadata-from-file="startup-script=deploy/startup.sh,compose-file=deploy/delivery/compose.yml"
```

While it boots (2–4 minutes), write down everything **you** chose or must look after for this VM. Look at the command and at `deploy/startup.sh`. Hint: there are at least six things (operating system, …).

Console check: **Compute Engine → VM instances**. Find `delivery-app`: status (green tick), zone, machine type, internal and external IP. Click it and look at the **Details** tab (boot disk, service account, labels, metadata) and the **Observability** tab (CPU, network).

🔍 **Challenge:** once it's up, get a shell **inside** the VM. Find out how on your own (console or `gcloud`). Then look at the delivery app's logs from in there:

```bash
sudo docker logs -f delivery_app      # Ctrl+C to stop
```

## 2.2 PaaS: an orders API on Cloud Run

`orders_api/` is a small FastAPI app: `POST /orders` accepts an order and publishes it to `order-events`. We give Cloud Run only the **source code**. Google builds the container, runs it, gives it an HTTPS address and adds or removes copies depending on traffic.

```bash
gcloud run deploy orders-api \
  --source=orders_api \
  --region="$REGION" \
  --service-account="$SA_DEFAULT" \
  --no-allow-unauthenticated \
  --max-instances=5 \
  --labels="${LABELS},app=orders-api"
```

The first time, `gcloud` asks to create an Artifact Registry repository called `cloud-run-source-deploy` for the built images: answer **Y**. The build takes 2–3 minutes.

```bash
export ORDERS_API_URL=$(gcloud run services describe orders-api --region="$REGION" --format='value(status.url)')
echo $ORDERS_API_URL

# the service is private (--no-allow-unauthenticated), so we send our identity token
TOKEN=$(gcloud auth print-identity-token)
curl -s -H "Authorization: Bearer $TOKEN" "$ORDERS_API_URL/"
curl -s -X POST "$ORDERS_API_URL/orders" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"customer_id": 3, "total_price": 59.9}'
```

> Paste the URL into `ORDERS_API_URL` in your `config.env`: we use it again on day 2.

Did the delivery VM receive the order? (The VM sends its logs to Cloud Logging, as in Project Setup.)

```bash
gcloud logging read 'logName:"gcplogs-docker-driver"' --freshness=10m --limit=10 \
  --format="value(timestamp,jsonPayload.message)"
```

Console check: **Cloud Run → Services → orders-api**.

- **Metrics:** your requests show up (request count, latency, number of container instances).
- **Revisions:** every deploy creates a new revision; traffic goes 100 % to the latest one.
- **Logs:** the app's output, without any SSH.
- Where did the container come from? **Cloud Build → History** shows the build Google ran for you, and **Artifact Registry → cloud-run-source-deploy** stores the image.

There is no VM anywhere in **Compute Engine** for this app.

What did **you** manage this time? Compare with your IaaS list.

## 2.3 FaaS: the delivery logic as a function

`functions/delivery/main.py` contains the same delivery simulation as `delivery-app`, but as a **function**. There is no loop and no server: Google calls `handle_order()` once for every message published to `order-events`.

Two steps: deploy the function as a private HTTPS endpoint, then connect it to `order-events` with a **push subscription**. Pub/Sub then calls the function once for every new message.

```bash
gcloud functions deploy delivery-function \
  --gen2 \
  --runtime=python312 \
  --region="$REGION" \
  --source=functions/delivery \
  --entry-point=handle_order \
  --trigger-http \
  --no-allow-unauthenticated \
  --service-account="$SA_DEFAULT" \
  --max-instances=10 \
  --memory=256Mi \
  --timeout=60s \
  --update-labels="${LABELS},app=delivery-function"

export FUNCTION_URL=$(gcloud functions describe delivery-function --region="$REGION" --format='value(url)')

gcloud pubsub subscriptions create delivery-function-sub \
  --topic=order-events \
  --push-endpoint="$FUNCTION_URL" \
  --push-auth-service-account="$SA_DEFAULT" \
  --ack-deadline=60 \
  --labels="$LABELS"
```

- `--service-account`: the identity the function **runs as**. It publishes to `delivery-events`.
- `--push-auth-service-account`: the identity Pub/Sub uses to **call** the function. It attaches a token of this service account to every request.
- `--ack-deadline=60`: Pub/Sub waits up to 60 s for the function's answer before it sends the message again. One delivery takes about 12 s.
- `--max-instances=10`: an upper limit, to protect your budget.

Send an order and read the function's logs:

```bash
curl -s -X POST "$ORDERS_API_URL/orders" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" -H "Content-Type: application/json" \
  -d '{"customer_id": 7, "total_price": 12.5}'

gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="delivery-function"' \
  --freshness=10m --limit=10 --format="value(timestamp,textPayload)"
```

Console check:

- **Cloud Run → Services:** `delivery-function` appears next to `orders-api`. A Cloud Run function is a Cloud Run service underneath; Google built the container from your `main.py`.
- Open it: **Metrics** shows one request per order, **Logs** shows the deliveries.
- **Pub/Sub → Subscriptions:** `order-events-sub` is of type **Pull** (the VM asks for messages), `delivery-function-sub` is **Push** (Pub/Sub calls the function).

> 💡 The order was delivered **twice**: once by the VM, once by the function. `order-events` now has two subscriptions (`order-events-sub` and `delivery-function-sub`), and **every subscription receives a copy** of every message. In a real system you would keep only one consumer. Here we keep both on purpose, to compare them on day 2.

## 2.4 SaaS: nothing to deploy

With SaaS you don't run anything: you use a finished product through a browser or an API. Which SaaS products have you already used in this master? Which ones does a data team typically use?

## 2.5 Compare

Fill in this table in pairs. We go through it together afterwards.


|                                        | IaaS (VM) | PaaS (Cloud Run) | FaaS (function) | SaaS |
| ---------------------------------------- | ----------- | ------------------ | ----------------- | ------ |
| What did you hand over?                |           |                  |                 |      |
| Who patches the operating system?      |           |                  |                 |      |
| Who installs Python and Docker?        |           |                  |                 |      |
| How does it handle 10× more traffic?  |           |                  |                 |      |
| What do you pay when no orders arrive? |           |                  |                 |      |
| What can you still control/customise?  |           |                  |                 |      |

## Cleanup (end of day 1)

```bash
gcloud compute instances delete delivery-app --zone="$ZONE" --quiet
```

**Keep** `orders-api` and `delivery-function`: they scale to zero and cost nothing while idle. We use them on day 2.

## Troubleshooting


| Symptom                                                                                   | Fix                                                                                                                                                                         |
| ------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Build fails with a permission error on the Cloud Build or Compute default service account | You can't fix this with the Editor role: tell your teacher, who asks the project's Owner (EDEM) to grant `roles/cloudbuild.builds.builder` to `$SA_DEFAULT`.                |
| `403` when calling the API with a token                                                   | Wait a minute after deploying, then get a fresh token: `TOKEN=$(gcloud auth print-identity-token)`.                                                                         |
| The function never runs                                                                   | Check the subscription and its endpoint: `gcloud pubsub subscriptions describe delivery-function-sub --format="value(pushConfig.pushEndpoint)"` must print `$FUNCTION_URL`. |
| `NOT_FOUND` for `order-events`, the subscription or the image                             | You skipped 2.0: run `./scripts/catch-up.sh`.                                                                                                                               |
| `PERMISSION_DENIED` in the logs, or the VM never pulls its image                          | The app doesn't run as `$SA_DEFAULT`: check that `PROJECT_NUMBER` is filled in, `source config.env`, and create it again.                                                   |
