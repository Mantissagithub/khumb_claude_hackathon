"""Operator/Claude-set deployments the simulation reacts to.

A :class:`Deployment` turns a :class:`shared.schema.DeploymentPlan` (geo coords)
into physics the engine consumes via the ``Controllables`` protocol:

    * police units (constable / squad)  -> soft repellers that enforce spacing
      and shave local crowd pressure
    * barricades / barriers             -> metering gates that hold the crowd and
      release it in batches (the real Kumbh "hold-and-release" technique), capping
      flow into the throat
    * CCTV re-aims                      -> change camera headings used by the
      coverage metric (sensing, not physics)
"""

from .deployment import POLICE_PARAMS, Deployment

__all__ = ["Deployment", "POLICE_PARAMS"]
