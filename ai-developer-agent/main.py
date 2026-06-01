import json
# pyrefly: ignore [missing-import]
from langgraph.graph import StateGraph, START, END
# pyrefly: ignore [missing-import]
from state import GraphState
from functools import partial
from architect import architect_agent

#langGraph workflow
workflow = StateGraph(GraphState)

#add nodes
workflow.add_node("architect_node", architect_agent)

#add edges
workflow.add_edge(START,"architect_node")

#flow end
workflow.add_edge("architect_node",END)

#compile
app = workflow.compile()

sample_srs_json = """
{
  I want to build a hyper-local community app called 'Neighborly' where people can rent out tools, share backyard produce, and hire locals for quick chores. When a user logs in, they should see a personalized feed of what’s happening within a 5-mile radius of their home address. Neighbors should be able to list items—like a lawnmower or extra mangoes from their tree—set a price per day, or mark it as free.

If someone wants to rent a lawnmower, they should request a booking timeframe. We need a way to lock the money in place safely so the lender knows they will get paid, but the borrower doesn't lose cash if the lender ghosts them. Once both parties agree, they need to text each other inside the app to arrange the handoff safely without revealing their real phone numbers. We also need a feedback loop where they rate each other's friendliness and reliability, which builds a community trust score visible on their profiles.

Furthermore, if someone needs a chore done, like cleaning gutters, they post a request with pictures, and local gig-workers can submit bids on how much they’ll charge. Finally, I need a massive back-office control panel for our internal safety team to review reported items, flag fraudulent profiles, handle refund disputes, and check platform transaction fees
}
"""

if __name__ == "__main__":
    print("=== AI Developer Agent  ===")
 
    #provide sample json input
    initial_state = {'srs_input': sample_srs_json}

    final_output = app.invoke(initial_state)

    #print final output
    print("\n--- [ARCHITECT OUTPUT] ---")
    print(json.dumps(final_output['microservices'], indent=2))

    print("\n=== Workflow Completed ===")
