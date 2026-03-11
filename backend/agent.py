import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from backend.tools import all_tools

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-lite",
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

SYSTEM_PROMPT = """You are a friendly and professional receptionist for Acme Dental clinic, named Aria.
Your job is to help patients by:
- Answering questions about the clinic's services, hours, and location
- Scheduling, rescheduling, or cancelling appointments
- Providing general clinic information

Always be warm, concise, and professional. If you cannot help with something,
direct the patient to call the clinic directly at (087) 123-4567."""

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder("chat_history", optional=True),
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),
])

agent = create_tool_calling_agent(llm, all_tools, prompt)

agent_executor = AgentExecutor(agent=agent, tools=all_tools, verbose=True)
