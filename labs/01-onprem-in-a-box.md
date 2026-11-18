# Lab 1 – On-prem in a box

**Goal:** experience what running software “on-premises” means. Your laptop plays the role of your company's **server room**, and each container plays one **server**.

*On-premises* (on-prem) means the company owns and runs its own computers, in its own building or in a rented data centre. Nobody else will fix them at 3 a.m.

## 1.1 Start your server room

```bash
cd 2627-gcp-cloud-intro
docker compose -f onprem/compose.yml up -d --build
docker compose -f onprem/compose.yml ps
```

You just “installed” five servers:


| Container        | Role in a real company                       | Real-world equivalent                                                               |
| ------------------ | ---------------------------------------------- | ------------------------------------------------------------------------------------- |
| `operational_db` | **Database server**: stores every order      | A physical server running PostgreSQL                                                |
| `pubsub`         | **Message broker**: the mailbox between apps | A server running a broker (RabbitMQ, Kafka…). Here we use Google's local emulator. |
| `orders-app`     | **Application server** placing orders        | A server running our Python program                                                 |
| `delivery-app`   | **Application server** delivering orders     | Another server running our Python program                                           |
| `adminer`        | **Admin tool** to look inside the database   | What the IT team uses to check data                                                 |

> `pubsub-init` creates the mailboxes (topics and subscriptions) and then exits. It's normal that it shows as *Exited*.

## 1.2 Watch the shop work

Follow both applications (`Ctrl+C` stops following, not the apps):

```bash
docker compose -f onprem/compose.yml logs -f orders-app delivery-app
```

You should see `Order N inserted successfully` from the orders app, then `Delivering order N` from the delivery app.

Now look inside the database. Open [http://localhost:8080](http://localhost:8080) and log in:


| Field               | Value               |
| --------------------- | --------------------- |
| System              | PostgreSQL          |
| Server              | `operational_db`    |
| Username / Password | `user` / `password` |
| Database            | `ecommerce`         |

Open the `orders` table and click **Select data**. Refresh after a minute: the shop keeps selling.

## 1.3 Scenario: a server breaks

The delivery server crashes:

```bash
docker compose -f onprem/compose.yml stop delivery-app
```

Wait **2 minutes**. Are orders still being accepted? (Check Adminer.) Where do the “order placed” notes go while nobody delivers?

Now repair the server:

```bash
docker compose -f onprem/compose.yml start delivery-app
docker compose -f onprem/compose.yml logs -f delivery-app
```

The delivery app catches up with every order it missed: the mailbox (message broker) kept them.

🤔 **Discuss:** in a real server room, who notices that the delivery server is down? At 3 a.m. on a Sunday? How long until a replacement arrives?

## 1.4 Scenario: Black Friday

Five times more customers arrive:

```bash
docker compose -f onprem/compose.yml up -d --scale orders-app=5
docker stats --no-stream
```

Compare the newest order with the newest delivery:

```bash
docker compose -f onprem/compose.yml logs --no-log-prefix orders-app | grep inserted | tail -1
docker compose -f onprem/compose.yml logs --no-log-prefix delivery-app | grep Delivering | tail -1
```

Repeat after a minute: the gap grows. One delivery app handles one order at a time (about 5 per minute) and can't keep up. Add more delivery servers:

```bash
docker compose -f onprem/compose.yml up -d --scale orders-app=5 --scale delivery-app=3
```

🤔 **Discuss:**

- Scaling worked here because your laptop had spare CPU and memory. What if you needed **50** delivery servers?
- On-prem you'd have to **buy** them. Buying, shipping and installing servers usually takes weeks. Black Friday is over by then.
- And in January? You own 50 servers that sit idle for 11 months.

Back to normal:

```bash
docker compose -f onprem/compose.yml up -d --scale orders-app=1 --scale delivery-app=1
```

## 1.5 Scenario: fire in the server room

```bash
docker compose -f onprem/compose.yml down -v      # -v also deletes the database disk
docker compose -f onprem/compose.yml up -d
```

Check Adminer again: every order is gone, and order numbers start at 1 again.

🤔 **Discuss:** what would have saved the data? Backups, but where? In the same room? A second building? Who pays for it?

## 1.6 Reflection: what would it take to run this for real?

In groups, list everything a company needs to run this shop on-prem, 24/7, for real customers. Your laptop played the server room in this lab. What would the real one need?

Try to go beyond the obvious: think about what you buy, where it lives, who looks after it, how long things take, and when you pay.

Keep your list: we use it in the next theory block (CAPEX vs OPEX).

## Cleanup

```bash
docker compose -f onprem/compose.yml down -v
```
