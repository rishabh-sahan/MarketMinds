from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from marketminds.agents.utils.agent_utils import (
    build_instrument_context,
    get_balance_sheet,
    get_cashflow,
    get_fundamentals,
    get_income_statement,
    get_language_instruction,
)


def create_fundamentals_analyst(llm):
    def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
        ]

        system_message = (
            "You are a researcher tasked with analyzing fundamental information over the past week about a company. Please write a comprehensive report of the company's fundamental information such as financial documents, company profile, basic company financials, and company financial history to gain a full view of the company's fundamental information to inform traders. Make sure to include as much detail as possible. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
            + " Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."
            + " Use the available tools: `get_fundamentals` for comprehensive company analysis, `get_balance_sheet`, `get_cashflow`, and `get_income_statement` for specific financial statements."
            + " INDIAN MARKET CONTEXT — this is an NSE/BSE listing, so report it the way an Indian analyst would. State every figure in rupees using lakh/crore conventions as the filings do, and never convert to dollars. Cover, where the data supports it: promoter holding and any change in it, pledged promoter shares, institutional holding split between FII and DII, related-party transactions, and standalone versus consolidated results. Note the fiscal year runs April to March, so 'FY26' means the year ending March 2026 and 'Q1' is the June quarter. Where a peer comparison helps, compare against Indian listed peers rather than global ones."
            # Anti-fabrication guard. Without this, a tool response like
            # "No data found for symbol 'X'" combined with the "include as
            # much detail as possible" instruction above pressures the model
            # into inventing a full financial profile — observed live on a
            # mistyped ticker, where it produced a CEO name, employee count,
            # market cap, P/E, EPS, and book value out of nothing and
            # described them as "successfully retrieved".
            + " CRITICAL — never invent financial data. Every figure you report must come"
            " verbatim from a tool response in this conversation. If a tool returns an"
            " error, a 404, or a 'no data found' message, that data does NOT exist: say so"
            " explicitly, name the tool and ticker that failed, and omit the section"
            " entirely rather than estimating, inferring, or recalling it from memory."
            " If the ticker cannot be resolved by any tool, state that the ticker appears"
            " invalid, suggest the likely correct symbol including its exchange suffix, and"
            " report no fundamentals at all. A short report that says data is unavailable is"
            " correct and useful; a detailed report containing invented numbers is a serious"
            " failure that could cause a real financial loss."
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    "For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "fundamentals_report": report,
        }

    return fundamentals_analyst_node
