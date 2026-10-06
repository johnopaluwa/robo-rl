# Business Plan: Customers First, Investors Second

Core idea: you don't need Physical Intelligence's $11B war chest. You need
ONE real business to pay you for solving ONE repetitive, dull problem, using
a robot that is allowed to be imperfect behind the scenes (teleop fallback)
as long as the outcome is reliable.

## 1. Target customers (picking/sorting niche)

Prioritize local, mid-sized, operationally-stressed businesses — not large
enterprises (too slow, procurement-heavy) and not tiny shops (no budget).

Good fits to approach first:
- Recycling sorting facilities (single-stream separation of one material)
- Small/mid e-commerce fulfillment operations (pick one SKU type from bins)
- Co-packing / small food & beverage assembly lines (tray loading, capping, sorting)
- Local manufacturing/light-assembly shops (defect sorting, kitting)

Find them via local business directories/maps search for terms like
"co-packing near me," "fulfillment center [your city]," "recycling sorting
facility [your region]," "commercial bakery near me."

## 2. The zero-risk pitch (use this almost verbatim)

> "Hi [Owner Name], I know how hard it is right now to hire and keep reliable
> people for [specific repetitive task]. I'm building an automation system
> for exactly this. I'd like to put it in your facility for two weeks,
> completely free. It needs zero changes to your floor. If it doesn't save
> you time, I take it away and you owe nothing. If it works, we can talk
> about a simple monthly subscription that's cheaper than a temp worker."

Don't sell "AI" or "reinforcement learning" — sell the removal of a specific
headache (staffing, turnover, missed throughput).

## 3. The "Wizard of Oz" bridge (your Angular advantage)

Your model will not be 100% autonomous on day one, and that's fine:
- If the policy's confidence drops below a threshold on a given grasp, it
  pauses instead of guessing.
- Your Angular dashboard flags this in real time with the camera view.
- You (or a cheap remote assistant) click to resolve it.
- The customer sees a job getting done reliably; you collect real-world
  data to keep improving the policy, and your intervention rate becomes a
  concrete, trackable metric that should fall over time.

This is standard practice, not a trick — document your intervention rate
honestly; a falling intervention-rate chart over the pilot is itself a great
proof point.

## 4. Pricing model: RaaS (Robotics-as-a-Service)

- Don't sell hardware outright (too expensive for a small customer up front,
  and too much commitment for you pre-product-market-fit).
- Lease the system for a flat monthly fee, pitched against the cost of a
  temp worker or an unfilled shift, e.g. **$500-2,500/month** depending on
  task complexity and value delivered, for an initial pilot.
- Criteria for a good target problem:
  1. "Dull, dirty, or dangerous" — a task people quit over, not a "cool demo" task
  2. Fits existing infrastructure — bolts onto an existing table/line, no remodel
  3. Clear, bulletproof UI — the customer's staff only ever needs START / STOP / CALL SUPPORT

## 5. Funding tiers (only pursue once you have something real to show)

| Tier | What the video/pitch shows | Typical raise |
|---|---|---|
| Proof of concept | Robot repeats task reliably in your own workspace, on cheap hardware, with your Angular dashboard monitoring it | $250K–$500K (angels, hardware accelerators) |
| Pilot deploy | Same, but on-site at a real business, under real conditions, ideally with a signed Letter of Intent | $500K–$1.2M (early deep-tech/pre-seed funds) |
| Autonomous scalability | Complex task, graceful recovery from disturbances, a fleet-management view across multiple units, a live paid RaaS contract | $1.2M–$2M+ (seed-stage VC) |

What investors will specifically check: is the video one continuous,
unedited take (not spliced clips); how often you intervened via
teleoperation during that take; and whether they can log into your
dashboard themselves and trigger a real action on the physical robot. If you
can let someone across the world click a button in your Angular dashboard
and watch the robot respond, that is extremely persuasive.

## 6. After raising (or after revenue lets you hire)

1. Hire a senior RL/robotics engineer to harden the policy and sim-to-real pipeline.
2. Hire a mechatronics engineer for reliable grippers/enclosures/electrical.
3. You stay as the software architect + product/business lead — scale the
   Angular fleet dashboard into a real multi-robot monitoring product.
4. Move from hobbyist hardware to leased/financed industrial cobots (UR,
   Doosan, Fanuc) once revenue justifies it.
5. Build the data flywheel: every pilot/customer hour of real-world data
   feeds back into retraining, pushing the human-intervention rate down and
   the case for the next customer up.

## Traps to avoid

- Over-polishing the AI in the lab instead of getting into a real site.
- Feature creep — mastering one task fully beats half-supporting two.
- Ignoring support — a robot idle for two days kills customer trust; your
  dashboard's alerting is a product feature, not an afterthought.
- Copying Physical Intelligence's "no timeline for commercialization"
  strategy — that only works with hundreds of millions in the bank; as a
  solo founder, revenue (even small) is your leverage and your proof.
