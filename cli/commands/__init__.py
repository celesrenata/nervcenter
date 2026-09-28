# Import all command modules
from .status import status
from .ask import ask
from .entity import entity
from .changes import changes
from .goal import goal
from .task import task
from .agents import agents
from .compute import compute
from .routes import routes
from .incident import incident

__all__ = [
    'status',
    'ask',
    'entity',
    'changes',
    'goal',
    'task',
    'agents',
    'compute',
    'routes',
    'incident'
]