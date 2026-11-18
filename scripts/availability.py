"""Composite availability calculator.

- Components that ALL must work (in series): multiply their availabilities.
- Redundant copies (in parallel): 1 - (1 - a) ** n  -> the system fails only if all copies fail.

Edit the scenarios at the bottom and run:  python3 scripts/availability.py
"""
MINUTES_PER_MONTH = 30.44 * 24 * 60


def series(*availabilities):
    """All components are needed: the chain is as weak as all links together."""
    result = 1.0
    for a in availabilities:
        result *= a
    return result


def parallel(availability, copies):
    """Independent redundant copies: the system is down only if every copy is down."""
    return 1 - (1 - availability) ** copies


def downtime(availability):
    minutes = (1 - availability) * MINUTES_PER_MONTH
    return f'{minutes:6.1f} min/month ({minutes * 12 / 60:5.1f} h/year)'


def report(name, availability):
    print(f'{name:<48} {availability * 100:8.4f} %   {downtime(availability)}')


# SLA figures (monthly uptime objectives) - check https://cloud.google.com/terms/sla
VM_SINGLE = 0.999        # Compute Engine, single instance
VM_MULTI_ZONE = 0.9999   # Compute Engine, instances in multiple zones
PUBSUB = 0.9995          # Pub/Sub
CLOUD_RUN = 0.9995       # Cloud Run services and functions

if __name__ == '__main__':
    print('Nines cheat sheet')
    for a in (0.99, 0.999, 0.9995, 0.9999, 0.99999):
        report(f'  {a * 100:g} %', a)

    print('\nScenario A - Project Setup: orders VM -> Pub/Sub -> delivery VM')
    report('  A', series(VM_SINGLE, PUBSUB, VM_SINGLE))

    print('\nScenario B - orders-api (Cloud Run) -> Pub/Sub -> delivery MIG (2 zones)')
    report('  B', series(CLOUD_RUN, PUBSUB, VM_MULTI_ZONE))

    # TODO (Lab 5): add your own scenario C, e.g. two independent delivery VMs in parallel:
    # report('  C', series(VM_SINGLE, PUBSUB, parallel(VM_SINGLE, 2)))
