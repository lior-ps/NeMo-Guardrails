# Prompt Security Integration

[Prompt Security AI](https://prompt.security/?utm_medium=github&utm_campaign=nemo-guardrails) allows you to protect LLM interaction. This integration enables NeMo Guardrails to use Prompt Security to protect input and output flows.

## Setup

1. Ensure that you have access to Prompt Security API server (SaaS or on-prem).

2. Update your `config.yml` file to include the Private AI settings:

```yaml
rails:
  input:
    flows:
      - protect prompt
  output:
    flows:
      - protect response
```

Set the `PS_PROTECT_URL` and `PS_APP_ID` environment variables.

## Usage

Once configured, the Prompt Security integration will automatically:

1. Protect prompts before they are processed by the LLM.
2. Protect LLM outputs before they are sent back to the user.

The `protect_text` action in `nemoguardrails/library/prompt_security/actions.py` handles the protection process.

## Error Handling

If the Prompt Security API request fails, it's operating in a fail-open mode (not blocking the prompt/response).

## Notes

For more information on Prompt Security and capabilities, please refer to the [Prompt Security documentation](https://prompt.security/?utm_medium=github&utm_campaign=nemo-guardrails).