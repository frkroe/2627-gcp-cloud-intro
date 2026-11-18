# Lab 3 – Black Friday

**Goal:** send a burst of 200 orders and compare how a single VM and a function cope. Then see the difference between **scalability**, **elasticity**, **vertical** and **horizontal** scaling.

```bash
cd 2627-gcp-cloud-intro
source config.env       # ORDERS_API_URL must be filled in (Lab 2.2)
echo $ORDERS_API_URL
```

## 3.1 Get ready

Recreate the delivery VM you deleted at the end of day 1 (same command as Lab 2.1):

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

Console check: **Compute Engine → VM instances** shows `delivery-app` again, with a new external IP (the old VM is gone for good).

Wait until it delivers a test order (2–4 minutes):

```bash
curl -s -X POST "$ORDERS_API_URL/orders" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" -H "Content-Type: application/json" \
  -d '{"customer_id": 1, "total_price": 10}'
gcloud logging read 'logName:"gcplogs-docker-driver"' --freshness=5m --limit=5 --format="value(jsonPayload.message)"
```

Now both consumers receive every order: the VM through `order-events-sub`, the function through `delivery-function-sub`.

## 3.2 Predict

Each delivery takes about **12 seconds** (`processing` → `delivering` → `delivered`). The VM delivers one order at a time. The function can run up to **10** copies in parallel (`--max-instances=10`).

For 200 orders, estimate how long each one needs: _______ (VM) and _______ (function).

## 3.3 Fire!

Open a **second terminal** and start the progress monitor:

```bash
cd 2627-gcp-cloud-intro && source config.env
./scripts/delivery_progress.sh
```

In the first terminal, send the burst (standard Python, no virtual environment needed):

```bash
python3 scripts/order_burst.py --url "$ORDERS_API_URL" --count 200 --workers 20
```

Console check, right after the burst: **Pub/Sub → Subscriptions**. Open `order-events-sub` and `delivery-function-sub` and look at **Metrics → Unacked messages**: this is the queue of orders still waiting for each consumer. Come back every few minutes: which queue empties first?

## 3.4 Watch it scale

While the monitor runs, open the console:

- **Cloud Run → orders-api → Metrics**: *Container instance count* and *Request latency*. How many copies of the API did Google start to absorb the burst?
- **Cloud Run → delivery-function → Metrics**: *Container instance count*. Does it reach 10?
- **Compute Engine → VM instances → delivery-app → Observability**: CPU utilisation. Is the VM busy?

After ~5 minutes the function has delivered all 200 orders. The VM still has a long queue ahead of it: let it be, Pub/Sub keeps the messages safe.

🤔 **Discuss:**

- The VM's CPU is almost idle, yet it's slow. Why? (Hint: most of each delivery is *waiting*.)
- Who decided how many copies of the function to run? When did they disappear?

## 3.5 Vertical scaling: a bigger machine?

Let's give the VM 4× more CPU and memory:

```bash
gcloud compute instances stop delivery-app --zone="$ZONE"
gcloud compute instances set-machine-type delivery-app --zone="$ZONE" --machine-type=e2-standard-2
gcloud compute instances start delivery-app --zone="$ZONE"
```

- Console check: refresh **Compute Engine → VM instances** while the commands run. The status goes *Stopping* → *Stopped* → *Running*, and the machine type changes to `e2-standard-2`.
- The VM had to be **stopped**: downtime.
- Does it deliver faster now? Watch the monitor for a couple of minutes.

The app processes one order at a time, so a bigger machine doesn't help. **More copies** do (horizontal scaling): that's Lab 4.

Put it back to the small, cheap size:

```bash
gcloud compute instances stop delivery-app --zone="$ZONE"
gcloud compute instances set-machine-type delivery-app --zone="$ZONE" --machine-type=e2-micro
gcloud compute instances start delivery-app --zone="$ZONE"
```

## 3.6 Scale to zero

Wait 10–15 minutes without sending orders, then check *Container instance count* for `orders-api` and `delivery-function` again. It drops to **0**: you pay nothing while nobody buys. The VM is billed every second it runs, busy or not.

## Summary


|                                                                   | Single VM                                             | Cloud Run / functions          |
| ------------------------------------------------------------------- | ------------------------------------------------------- | -------------------------------- |
| Scalable? (*can* it grow?)                                        | Yes, but you decide and act: bigger machine, more VMs | Yes                            |
| Elastic? (does it grow **and shrink** automatically with demand?) | No                                                    | Yes, from 0 to `max-instances` |
| Cost when idle                                                    | Full price                                            | 0                              |

Keep the VM: Lab 4 replaces it with a group of VMs.
