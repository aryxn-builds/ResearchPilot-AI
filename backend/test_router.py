from app.llm.router import LLMRouter

err_str = """Error code: 400 - {'error': {'message': 'Failed to parse tool call arguments as JSON', 'type': 'invalid_request_error', 'code': 'tool_use_failed'}}"""

class DummyException(Exception):
    pass

e = DummyException(err_str)
print(LLMRouter._is_permanent_error(e))
