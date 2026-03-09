"""
AgentReplay + LangChain quickstart.

Requirements:
    pip install agentreplay[langchain] langchain-openai

Usage:
    OPENAI_API_KEY=sk-... python examples/langchain_quickstart.py
"""
import os

from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain import hub

from agentreplay.interceptors.langchain import AgentReplayCallback


@tool
def calculator(expression: str) -> str:
    """Evaluate a simple math expression. Input should be a valid Python expression."""
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))  # noqa: S307
    except Exception as e:
        return f"Error: {e}"


@tool
def word_count(text: str) -> str:
    """Count the number of words in a piece of text."""
    return str(len(text.split()))


def main() -> None:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    tools = [calculator, word_count]
    prompt = hub.pull("hwchase17/react")

    agent = create_react_agent(llm, tools, prompt)

    # One line to enable AgentReplay tracing
    cb = AgentReplayCallback(run_name="langchain-quickstart")

    executor = AgentExecutor(agent=agent, tools=tools, verbose=False)
    result = executor.invoke(
        {"input": "What is 1234 * 5678? Then count how many words are in that number when written out."},
        config={"callbacks": [cb]},
    )

    print(f"\nResult: {result['output']}")

    # Open the dashboard
    cb.serve()
    print("\nDashboard open at http://localhost:7474")
    print("Press Ctrl+C to stop.")

    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
