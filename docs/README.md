# Documentation

Start with the first two. The rest are references for one topic each.

| Document | Read it when you want to |
| --- | --- |
| [../README.md](../README.md) | Run the project, see the configuration and the API at a glance |
| [architecture.md](architecture.md) | Understand how every part works and why |
| [telemetry-contract.md](telemetry-contract.md) | Send data: message format, limits, error codes (Spanish) |
| [models.md](models.md) | Know what each database record means and its rules (Spanish) |
| [decisions.md](decisions.md) | See what was decided, when, and why (Spanish and English) |
| [deploy-railway.md](deploy-railway.md) | Deploy or change the hosted site |
| [dosimeter.md](dosimeter.md) | Use the dedicated dosimeter simulator and the NASA context |
| [combined-reports.md](combined-reports.md) | Export one report with vital signs and dosimetry |
| [sensor-sending-scenario.md](sensor-sending-scenario.md) | Follow one device from setup to stored readings |
| [endpoint-tests.md](endpoint-tests.md) | See which routes exist and what the tests cover |
| [../monitoring/tests/README.md](../monitoring/tests/README.md) | Run the tests, all or one area |
| [../ia/README.md](../ia/README.md) | Use the summary module and its language models (Spanish) |
| [../landing/README.md](../landing/README.md) | Work on the landing page |

`AGENTS.md` at the repository root holds the working rules for the project: scope, safety limits and acceptance criteria.

## Words used across the documents

| Term | Meaning |
| --- | --- |
| Session | A period of monitoring for one participant |
| Packet | One message from a device; all its readings share one capture time |
| Reading, measurement | One value from one sensor |
| `observed_at` / `received_at` | When the instrument captured it / when the server got it |
| Provenance, source | Whether data is `simulated` or from `hardware` |
| Baseline | How the person was at the start of the session; what later readings are compared with |
| Counter epoch | One life of a cumulative counter, between two resets |
| DIS chamber | One of the dosimeter's two ion chambers, each a counter of its own |
| RBE | Radiation-belt enhancement, a NASA space-weather event |
