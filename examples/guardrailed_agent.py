"""Agent with input/output guardrails."""

from pydantic_ai import Agent

from agent_sdk import GuardrailResult, Runner, input_guardrail


agent = Agent('test', system_prompt='You are a helpful assistant.')


@input_guardrail('content-filter')
async def block_harmful(data: str, ctx: object) -> GuardrailResult:
    """Block prompts containing prohibited content."""
    prohibited = ['harmful_content']
    if any(p in data.lower() for p in prohibited):
        return GuardrailResult(passed=False, tripwire=True, reason='Prohibited content detected')
    return GuardrailResult(passed=True)


runner = Runner(agent, guardrails=[block_harmful])

if __name__ == '__main__':
    # This will work fine
    result = runner.run_sync('Tell me about Python.')
    print(f'Output: {result.output}')

    # This would raise GuardrailTripwireError
    # result = runner.run_sync('Tell me about harmful_content')
