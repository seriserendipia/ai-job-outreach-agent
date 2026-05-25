"""Graph nodes."""
from app.graph.nodes.critic import critic
from app.graph.nodes.jd_analyzer import jd_analyzer
from app.graph.nodes.recruiter_finder import recruiter_finder
from app.graph.nodes.supervisor import supervisor
from app.graph.nodes.writer import writer

__all__ = ["supervisor", "jd_analyzer", "recruiter_finder", "writer", "critic"]
