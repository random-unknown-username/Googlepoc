console.log("SAFE_POC_MARKER: attacker-controlled fork code executed inside privileged workflow_run");
console.log("FAKE_SECRET_PRESENT:", Boolean(process.env.FAKE_GEMINI_API_KEY));
console.log("FAKE_SECRET_LENGTH:", (process.env.FAKE_GEMINI_API_KEY || "").length);
console.log("GITHUB_REPOSITORY:", process.env.GITHUB_REPOSITORY);
console.log("GITHUB_EVENT_NAME:", process.env.GITHUB_EVENT_NAME);
