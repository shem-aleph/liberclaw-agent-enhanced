# Bump this when agent code changes in ways that require redeployment.
# Bumped to 5: fix persistent shell leaking fd 0 into child processes
# (ssh was swallowing sentinel bytes from bash's stdin pipe and hanging).
AGENT_VERSION = 5
