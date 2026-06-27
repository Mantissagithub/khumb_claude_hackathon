# Scalable Buildathon Solution Design — Chat Transcript

> Shared by Ashutosh. A copy of a chat between Claude and Ashutosh.
> Source: https://claude.ai/share/672b461d-16c2-44a6-ac8a-e42cca24132d
>
> **Note:** Several assistant replies in this chat produced interactive artifacts (full product plans, problem-statement cards, system maps, operational-problem maps). In the shared snapshot these render as *"Log in to see interactive visuals"* and their full contents are **not available** in the public share. What follows is the complete message thread plus all visible inline commentary.

---

## 1. User

> *(Files hidden in shared chats)*

This is the context. I'm attending a buildathon in this we have given a problem to solve. I want you to help me in the entire project. While thinking about think from top product designer who thinks about the users and also think from developer point of view I want solution at scale.

*(10:35)*

## Claude

I'd love to help you build something impactful for this buildathon! Let me make sure I understand the problem well before we dive in.

---

## 2. User

Q: What's your team's primary strength?
A: Design-heavy

Q: What do you want to build first?
A: Full product plan + architecture

Q: What's your target platform?
A: Not decided yet

*(10:36)*

## Claude

Perfect. Let me build you a comprehensive product plan. Given you're design-heavy, I'll make sure the UX thinking is central to everything.

Here's your full product plan — structured like a proper product brief with architecture, UX thinking, and build strategy baked in.

> *[Interactive artifact — "Log in to see interactive visuals"]*

Here's the key thinking behind this plan:

- **Why a PWA over a native app** — no install friction, works on any device at the venue, critical for a low-tech audience. Families under stress will not download an app.
- **Your UX edge is real** — the other teams will likely hack together a backend and call it done. A design-heavy team that ships a beautiful, Hindi-language, emotionally clear "find my child" screen will stand out completely.
- **MilaaP as a name** — it's not just branding, it's your pitch anchor. "मिलाप" means reunion in Hindi, resonates culturally, and makes the government stakeholders feel this was built for them.
- **PII is a trap for most teams** — address it proactively. Have a consent screen, explain embedding-only storage, and mention DPDP Act 2023 to the judges. They're specifically scoring this.
- **The demo moment** — script a single emotional story: grandmother gets separated at the ghaat → family uploads photo on phone → system finds match in 4 seconds → SMS sent. If judges see that live, you win.

Click any of the buttons at the bottom to go deep on any piece — I'd suggest starting with the public app UX if you want to play to your design strength.

---

## 3. User

> *(Files hidden in shared chats)*

This is more data about the problem statement and the context.

*(10:54)*

## Claude

This changes things significantly — the real problem is clearer now. Let me update the plan with this deeper context.

> *[Interactive artifact — "Log in to see interactive visuals"]*

Three things this dataset changes significantly:

1. **The real product is cross-center search, not facial recognition.** Face matching is a nice-to-have. The actual gap — a found person at Center B being invisible to a family at Center A — is solved with a well-designed fuzzy search registry. That's faster to build, more reliable in the field, and directly addresses the stated problem.
2. **The chokepoints data is a goldmine for your demo.** Overlay the 85 chokepoints + transfer nodes with case density from the CSV — you can literally show judges a map that says "these 3 transfer nodes generated 40% of all separations." That's a policy insight, not just a feature. It's memorable.
3. **Design for the operator, not the family.** The elderly, no-phone demographic means a volunteer at a kiosk is the actual user interface for most found people. Your family app is secondary to the help desk tablet experience. Get that right first.

Pick the button that matches where your team wants to start — I'd suggest operator app UX or Supabase schema + API as the first two parallel tracks to split your team across.

---

## 4. User

How can we help unite families at kumbh mela more efficiently.

This is the problem statement I've figured out lets refine it.

*(11:21)*

## Claude

Good instinct to refine it. But "unite families more efficiently" is still broad — let's pressure-test it against what the data actually tells us.

---

## 5. User

How can we make it more tailored.

*(11:22)*

## Claude

Great question — let me help you sharpen the problem statement into something specific, defensible, and emotionally resonant.

---

## 6. User

Give me problem statements that are more refined.

*(11:22)*

## Claude

Based on everything in the dataset and context, here are sharp, specific problem statements you can choose from — each targets a different angle:

> *[Interactive artifact — "Log in to see interactive visuals"]*

My honest recommendation is **#1 + #4 combined** — they're two sides of the same coin:

- **#1** is the technical problem: centers can't talk to each other
- **#4** is the human problem: families feel invisible and anxious

Together your problem statement becomes: *"Families searching for a missing pilgrim have no way to know if they've already been found and registered at another center — so they wander, re-file, and lose hours."*

That's specific, emotional, data-backed, and solvable in a hackathon. Click any card to go deep on that direction.

---

## 7. User

I want to go with problem statement 1: cross-center search gap. Help me build around this.

*(11:23)*

## Claude

Perfect choice. Let me now map out exactly what to build, screen by screen, decision by decision.

---

## 8. User

I want to refine more problem.

People are missing and the current method is operation intensive. So the current problem is the entire system works offline — police staff have centers where they file report for **lost** report (when I'm lost from my family) or **found** (is when family looking for a person). I want to help this system to be more efficient. One they file the report from family and the person lost, the way it finds someone is just people waiting for something to come to the center and see the person.

Need to refine the problem statement more in this direction.

*(11:31)*

## Claude

Now we're getting to the real insight. Let me reflect this back and sharpen it.

> *[Interactive artifact — "Log in to see interactive visuals"]*

The key word your team needs to internalize is **passive vs. active**.

The current system is entirely **passive** — it waits. A found person sits at Center B. A family waits at Center A. The match only happens if a human physically bridges the two. At 80 crore people across 32 zones, that human bridge almost never comes in time.

Your product flips it to **active** — the moment any report is filed anywhere, the system instantly searches everything and pushes a match to the operator. The family doesn't have to do anything after filing. The system comes to them.

That's the one sentence you repeat to the judges throughout your demo. Pick any of the three next steps to keep building.

---

## 9. User

Currently the method to find people is staff can do announcements, put photo of the lost person in the display and wait for someone to report and come.

*(11:33)*

## Claude

Now we have the complete picture. This is a crucial detail — let me add this to the system map.

> *[Interactive artifact — "Log in to see interactive visuals"]*

This detail about announcements and photo boards is actually your strongest demo argument. Because now you can tell judges:

> "The current system has 3 methods. All 3 are local, passive, and ephemeral. MilaaP replaces all 3 with one active, cross-center, persistent system."

That's a clean before/after story that anyone — technical or not — immediately understands.

The photo board insight is especially powerful. A display at Center A showing a found person is invisible to a family at Center B 2 km away. MilaaP makes that same photo visible to every operator across all 32 zones the second it's uploaded. Same idea, infinite reach.

Which piece do you want to build first?

---

## 10. User

Do a research on internet and tell me what are the operations problem these staff face in their task.

*(11:35)*

## Claude

*(Searched the web ×2)*

Good research collected. Let me now synthesize everything into a clear operational problems map for your team.

> *[Interactive artifact — "Log in to see interactive visuals"]*

Three findings from the research that should directly shape what you build:

1. **The 16-language problem is real.** At Nashik Kumbh 2015, volunteers had to make announcements in 16 different languages just to cover the linguistic diversity of pilgrims. Your app's language field in search isn't a nice-to-have — it's how staff identify someone who can't communicate their own name.
2. **The network collapse is documented.** Inadequate multilingual announcements and confusing signboards led to chaos, and agencies operated in silos delaying response. Any system that depends on internet during peak hours will fail exactly when it's needed most. Offline-first isn't optional.
3. **The inter-agency black hole is the 3% unresolved rate.** Facial recognition was described as "not foolproof" even by the police superintendent overseeing it — which means the registry and matching logic is what actually drives reunions, not AI vision alone. Your core feature is the right one.

The most important line for your judges: *"Seven operational problems. One root cause. Information trapped in silos."* That's MilaaP's entire pitch.

---

## 11. User

Now write the problem statement.

*(11:38)*

## Claude

Based on everything — the research, the dataset, the 7 operational problems, and the real workflow — here's your problem statement, written at three levels of detail you can use in different contexts.

> *[Interactive artifact — "Log in to see interactive visuals"]*

The last line of the full brief is the one to memorise and say to every judge:

> "The real problem is not that people can't be found. It's that the information to find them already exists — but it's trapped."

That single sentence does three things at once — it validates the current staff's effort (they're filing records), it identifies the gap precisely (no cross-center flow), and it makes your solution obvious before you even show it. Use the copy buttons to grab whichever version you need right now.

---

## 12. User

What are the real operation level problems of the staff.

*(11:42)*

## Claude

Let me go deeper — beyond what official sources say, into what actually happens on the ground.

*(Searched the web ×2)*

This is gold. Real on-the-ground accounts from actual volunteers. Now let me turn this into something actionable for your build.

> *[Interactive artifact — "Log in to see interactive visuals"]*

---

## Key takeaways across the chat

- **Product name:** MilaaP (मिलाप = "reunion") — used as both branding and pitch anchor.
- **Chosen problem statement:** #1, the *cross-center search gap* — combined with the human/emotional angle (#4): *"Families searching for a missing pilgrim have no way to know if they've already been found and registered at another center — so they wander, re-file, and lose hours."*
- **Core reframe:** current system is **passive** (wait at center, announcements, photo boards); MilaaP makes it **active** (any report filed anywhere instantly searches everything and pushes matches to operators across all 32 zones).
- **Primary user:** the **operator/volunteer at a help-desk kiosk**, not the family — because of the elderly, no-phone demographic. Family app is secondary.
- **Architecture leanings:** PWA over native app (no install friction, works on any device, offline-first because the network collapses at peak); fuzzy-search registry as the core, facial recognition only a nice-to-have.
- **Demo strategy:** a single emotional story (grandmother separated at the ghaat → family uploads photo → match in seconds → SMS sent); plus a chokepoint/transfer-node density map showing where separations cluster.
- **Compliance angle:** address PII proactively — consent screen, embedding-only storage, reference DPDP Act 2023.
- **Research findings:** 16-language announcement problem (Nashik Kumbh 2015), documented network/coordination collapse, agencies operating in silos, ~3% unresolved rate, facial recognition "not foolproof." Root cause: *"Seven operational problems. One root cause. Information trapped in silos."*
