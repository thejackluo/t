# Boston all-stations Guinness attempt: supplied rules

## Source and status

Source: the user pasted their Guinness World Records application guidelines into the project discussion on 2026-10-21. The heading is **“Fastest time to travel to all Boston subway stations.”** This is a structured extraction of that supplied text, not a replacement for the original application guidelines or a claim of independent verification.

The supplied application text supersedes earlier project research that could only locate an inactive public pre-2022 category. The application ID, guideline revision/date, target record time, and signed-agreement status were not supplied. No public-page lookup is needed to infer rules already present in this text.

The referenced **attached station-list image** and **Guide to Your Evidence** were not included. Do not manufacture the required inventory from a GTFS station count. Keep the original guidelines and eventual attachments as the authority; this document records requirements relevant to the application.

## Record and station coverage

1. The record may be attempted by an individual or team and is measured in hours, minutes, and seconds to the nearest 0.01 second.
2. The definition explicitly includes the **Silver Line bus rapid transit system**, as well as the Boston subway network.
3. Every required station must be visited. The supplied guidelines refer to an attached image for the full station list.
4. A normal visit requires arrival and/or departure on an underground train in normal public service, and the train must stop. Participants need not get off at intermediate stations. A drawn path or a walk through a station does not establish a qualifying visit.
5. Geographically separate, unlinked stations with the same name must each be visited. A station served by multiple lines need not be visited on each line. Not every stretch of track must be traversed; repeated visits/traversals are allowed.
6. Restricted station operating hours must be respected.
7. A temporarily closed station may be accepted by a non-stop pass-through under the general guidelines, with details and evidence. This is an explicit exception, not the normal rule.
8. A terminal closed for long-term repairs must still be visited, but may be both arrived at and departed from on foot or by scheduled surface public transport. Proof of closure is required.

### Interpretation gaps to retain

- **Silver visit predicate:** Silver is expressly required, while the generic visit and clock rules use “train.” Model Silver separately; obtain application-specific clarification before declaring a Silver visit or Silver start/finish compliant. Do not silently exclude it or apply an invented exception.
- **Inventory:** reconcile the attached list against dated MBTA station/boarding-stop identities, including station grouping and any changed service. The existing 125 rail parent stations are an imported dataset, not an approved Guinness total.
- **Closure exceptions and endpoints:** apply exception records with source, affected station, dates, permitted action, and evidence reference. Closure exceptions do not silently override the stated start/finish rules.
- **Participant age wording:** the supplied text says both “No person under the age of 18” and that persons aged 16–18 need parental/guardian permission. Preserve the inconsistency for clarification if relevant; do not resolve it by assumption.

## Official timing boundary

The supplied wording is:

> The clock must start the moment the doors close on the first train taken by the challengers. It must stop the moment the challengers set foot on the platform at the last station.

- All breaks, stops, and delays remain inside the continuous elapsed time. There is no paused record clock.
- Pre-start access and waiting for the first train are preparation, not automatically part of the record duration.
- Subsequent waits, running/walking, transfers, rides, and breaks count. The final alighting interval counts; final station exit does not extend the stated platform finish.
- Timetable departure/arrival fields are planning proxies, not observed door-closing/platform-footfall events. Label estimated start/finish allowances and do not imply centisecond forecast accuracy merely because the official measurement uses 0.01 seconds.
- The generic text supplies no same-station or loop requirement. The editor can retain free endpoints and optional pins, with any application-specific endpoint restriction stored separately.

## Permitted connector transport

- Transfers between metro lines may use **scheduled public transport or travel on foot**. Walking and running are foot transfers.
- Private motor vehicles, taxis, and privately arranged transport, including bicycles and skateboards, are prohibited.
- Permission in the rules is distinct from product support: the first rail editor supports foot/internal transfers; adding a scheduled bus or other public-transport connector requires its own dataset and implementation. Such a connector does not automatically earn subway-station coverage.

## Evidence and observation requirements

The supplied requirements include:

- Film the beginning and end clearly, and film the entire attempt so further footage can be provided if requested.
- The submitted highlights must show first-train doors closing with a visible timepiece, transfers on foot or scheduled public transport, and the finish on the final platform with a visible timepiece.
- Provide timestamped station evidence. The Boston-specific section permits timestamped video clips and/or photographs, while the general section explicitly requires an arrival photograph at each station with a digital timestamp or visible clock. Retain the stricter per-station photo requirement unless the application clarifies otherwise.
- Maintain a logbook with each station's arrival/departure, train number, line changes, connecting journeys, and every break/stoppage. Preserve intermediate calls, not just the endpoints of a drawn ride.
- Obtain chronological tickets/receipts for journeys with no significant evidence gaps; provide season-ticket details where applicable.
- Two independent persons witness the start and finish and confirm exact times. They need not be the same people at each end and need not accompany the entire journey.
- A witness starts the master stopwatch, and a witness stops it. Participants must not carry that master stopwatch; arrange transfer between witnesses if needed. A participant reference stopwatch is permitted.
- Obtain the two signed independent witness statements, originating from the witnesses themselves rather than pre-prepared participant statements, with contact details.
- Maintain an additional witness book with date/time, location, name, and signature where possible.
- Supply a cover letter with participant/organizer identities, date/time/location, measurement, preparation, and witnesses; route details; logs; tickets/receipts; photographs; and video. Media coverage is optional.
- Read the separate Guide to Your Evidence and its templates before submission.

The supplied legal notice also says authorization requires GWR's signed standard agreement. Planning an itinerary or meeting an application checklist is not an approval decision.

## Application implications

- Keep **planned**, **scheduled**, and **observed** events separate. A scheduled stop yields planned coverage; evidence of actual operation is needed for an attempt claim.
- Save the ruleset version, station inventory, dataset identity, connector permissions, and start/finish semantics with each scenario.
- Record closure exceptions explicitly; ordinary user exclusions must not make a record-complete badge appear.
- The first rail-only release must label its coverage **rail rehearsal**, not complete Guinness coverage. Silver remains required for the full attempt even while implementation is deferred; its Phase 7 designation in the archived roadmap is historical, not an active execution instruction.
- Attempt-day evidence tooling remains later work. Preserve stable station/leg/event identifiers now; keep raw evidence and personal witness details out of Git.
