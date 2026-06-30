# sip-plugins

The **plugin SDK** for Sovereign Inference. A third-party pip package can extend
the system — adding a runtime adapter, an external-compute provider, or a discovery
directory — by declaring Python **entry points**; this package discovers and
registers them.

A plugin author declares, in their `pyproject.toml`:

```toml
[project.entry-points."sip_ai.runtime_adapters"]
myruntime = "my_pkg:MyAdapter"

[project.entry-points."sip_ai.compute_providers"]
mycloud = "my_pkg:my_provider_factory"
```

A host then loads them:

```python
import sip_plugins
sip_plugins.load_all()            # registers everything installed
sip_plugins.discover("sip_ai.runtime_adapters")   # inspect without registering
```

A plugin that fails to import is **skipped, not fatal** — one bad plugin can't take
down the host. The entry-point source is injectable, so loading is unit-testable
without installing packages.

**Status:** implemented. **License:** Apache-2.0 — see [LICENSING.md](../../LICENSING.md).

Design refs: [Architecture](../../docs/architecture.md), [SIP-AI PRD](../../docs/prd/sip-ai.md).
