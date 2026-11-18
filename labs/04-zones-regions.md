# Lab 4 – Zones, regions and failures

**Goal:** make the delivery app survive the loss of a VM (or a whole zone), scale it horizontally, and measure what distance does to latency.

```bash
cd 2627-gcp-cloud-intro
source config.env
```

## 4.1 From one VM to a managed instance group

A **managed instance group (MIG)** keeps a number of identical VMs running from a **template**. A **regional** MIG spreads them across zones, so losing one zone doesn't take the app down.

```bash
# 1. The single VM is replaced by the group
gcloud compute instances delete delivery-app --zone="$ZONE" --quiet

# 2. A template: the same settings you used for the VM, without a name or zone
gcloud compute instance-templates create delivery-app-tpl \
  --instance-template-region="$REGION" \
  --machine-type=e2-micro \
  --image-family=debian-12 --image-project=debian-cloud \
  --boot-disk-size=10GB \
  --service-account="$SA_DEFAULT" \
  --scopes=cloud-platform \
  --labels="${LABELS},app=delivery" \
  --metadata="app-image=$REGISTRY/delivery-app:v1" \
  --metadata-from-file="startup-script=deploy/startup.sh,compose-file=deploy/delivery/compose.yml"

# 3. A group of 2 VMs, spread across two zones of Madrid
gcloud compute instance-groups managed create delivery-mig \
  --region="$REGION" \
  --zones="${REGION}-a,${REGION}-b" \
  --template="projects/$PROJECT_ID/regions/$REGION/instanceTemplates/delivery-app-tpl" \
  --size=2

gcloud compute instance-groups managed list-instances delivery-mig --region="$REGION"
```

Console check:

- **Compute Engine → Instance templates:** `delivery-app-tpl`. Open it and compare with the VM settings from Lab 2.1: machine type, image, service account, metadata.
- **Compute Engine → Instance groups → delivery-mig:** target size 2, the two zones, and the VMs it created. Their names start with `delivery-mig-` plus a random suffix.
- **Compute Engine → VM instances:** the group's VMs look like any other VM, but in a different zone each. `delivery-app` is gone.

Note the VM names and their **zones**. Both VMs read from the same subscription (`order-events-sub`). Pub/Sub hands each message to **one** of them, so they share the work.

## 4.2 Break a VM

Wait until both VMs are running (2–4 minutes). Then “lose” one of them:

```bash
gcloud compute instances delete <one-of-the-vm-names> --zone=<its-zone> --quiet

# repeat a few times over the next minutes
gcloud compute instance-groups managed list-instances delivery-mig --region="$REGION"
```

Even better, watch it in the console: keep **Compute Engine → Instance groups → delivery-mig** open and refresh. The deleted VM disappears, then comes back with status *Provisioning* → *Running*.

The group notices that a VM is missing and **recreates it** automatically: same name, same template. This is called **self-healing**. Meanwhile the other VM, in the other zone, keeps delivering.

🤔 **Discuss:** what would happen with the single VM from Project Setup if its zone went down? What if the whole **region** went down?

## 4.3 Horizontal scaling

Scale out to 4 VMs and send another burst:

```bash
gcloud compute instance-groups managed resize delivery-mig --size=4 --region="$REGION"
```

Console check: **Instance groups → delivery-mig** shows target size 4. On **VM instances**, which zones did the two new VMs land in?

Wait until the new VMs are running, then in two terminals:

```bash
./scripts/delivery_progress.sh
```

```bash
python3 scripts/order_burst.py --url "$ORDERS_API_URL" --count 100 --workers 20
```

Compare the VM column with Lab 3: four VMs deliver about four times faster than one. Horizontal scaling works, but **you** chose the number. With an autoscaler, the group could choose for you, based on CPU or on the Pub/Sub backlog.

Scale back down:

```bash
gcloud compute instance-groups managed resize delivery-mig --size=2 --region="$REGION"
```

## 4.4 Regions: distance costs time

Deploy a second copy of `orders-api` in Tokyo (`$FAR_REGION`):

```bash
gcloud run deploy orders-api \
  --source=orders_api \
  --region="$FAR_REGION" \
  --service-account="$SA_DEFAULT" \
  --no-allow-unauthenticated \
  --max-instances=2 \
  --labels="${LABELS},app=orders-api"

export FAR_URL=$(gcloud run services describe orders-api --region="$FAR_REGION" --format='value(status.url)')
```

Console check: **Cloud Run → Services** now lists `orders-api` twice. Look at the **Region** column: `europe-southwest1` (Madrid) and `asia-northeast1` (Tokyo). Same code, same name, two independent services with their own URLs.

Measure the response time from your laptop to each region (the first call of each may be slow: a cold start):

```bash
TOKEN=$(gcloud auth print-identity-token)
for URL in "$ORDERS_API_URL" "$FAR_URL"; do
  curl -s -H "Authorization: Bearer $TOKEN" "$URL/"; echo
  for i in 1 2 3 4 5; do
    curl -s -o /dev/null -w "  %{time_total}s\n" -H "Authorization: Bearer $TOKEN" "$URL/health"
  done
done
```

Also try <https://gcping.com>: it measures your latency to every Google Cloud region.

🤔 **Discuss:**

- Madrid vs Tokyo: how many milliseconds apart? Why does it matter for a web shop? And for a nightly batch job?
- The Tokyo API publishes to the **same** Pub/Sub topic. Pub/Sub is a global service. Our Spanish customers' orders would now be processed in Japan. Is that allowed? (GDPR, data residency.)
- Name three things that decide which region a company picks.

## Cleanup

```bash
gcloud run services delete orders-api --region="$FAR_REGION" --quiet
```

Keep `delivery-mig` until the end of Lab 5, or delete it now if you're done for the day:

```bash
gcloud compute instance-groups managed delete delivery-mig --region="$REGION" --quiet
```
