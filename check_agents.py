from myagent.agent import root_agent

print(f"Router Agent: {root_agent.name}")
print(f"Router Tools: {[t.name if hasattr(t, 'name') else str(t) for t in root_agent.tools]}")
print("Sub-agents:")
for sub in root_agent.sub_agents:
    print(f"  - {sub.name} (model: {getattr(sub.model, 'model_name', sub.model) if hasattr(sub, 'model') else 'unknown'})")
print("Agent graph loaded successfully!")
