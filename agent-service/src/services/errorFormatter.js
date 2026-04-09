class ErrorFormatter {
  summarize(error = '') {
    const message = String(error || '').trim();
    if (!message) {
      return 'The run failed without a detailed error message.';
    }

    if (/Command timed out after (\d+)s/i.test(message)) {
      const seconds = message.match(/Command timed out after (\d+)s/i)?.[1] || 'unknown';
      return `A terminal command took longer than ${seconds}s. Increasing the timeout or reducing the work for that step should help.`;
    }

    if (/Ollama generation timed out after (\d+)s/i.test(message)) {
      const seconds = message.match(/Ollama generation timed out after (\d+)s/i)?.[1] || 'unknown';
      return `The selected model took longer than ${seconds}s to answer. Try a smaller model or a longer timeout.`;
    }

    if (/Missing required files:/i.test(message)) {
      const files = message.split('Missing required files:')[1]?.trim() || 'required files';
      return `The AI skipped required files for this service: ${files}.`;
    }

    if (/does not resolve to a generated file/i.test(message)) {
      return 'The AI created an import that points to a file that does not exist in the generated service.';
    }

    if (/internal service names must not be installed from npm/i.test(message)) {
      return 'The generated package.json tried to install one of your microservice names as if it were an npm package.';
    }

    if (/npm install failed/i.test(message)) {
      return 'Package installation failed. The logs usually show whether it was a timeout, missing package, or dependency conflict.';
    }

    if (/Validation failed for/i.test(message)) {
      return message.replace(/^Validation failed for [^:]+:\s*/i, '').trim();
    }

    return message;
  }
}

module.exports = new ErrorFormatter();
