# SonarCloud and Snyk setup

This branch contains CI-based SonarCloud and Snyk scanning for the Agent 4 backend and frontend.

## Added files

- `.github/workflows/sonarcloud.yml`
- `.github/workflows/snyk.yml`
- `sonar-project.properties`

## 1. Connect SonarCloud

1. Sign in to SonarQube Cloud using the GitHub account that can access `Ravindu200232/RP-SE-009`.
2. Import the `RP-SE-009` repository.
3. Select **GitHub Actions / CI-based analysis**. Do not run automatic analysis at the same time.
4. Confirm these values in SonarCloud:
   - Project key: `Ravindu200232_RP-SE-009`
   - Organization key: `ravindu200232`
5. If SonarCloud generated different values, update `sonar-project.properties` to use the exact displayed keys.
6. In SonarCloud, create a project analysis token.
7. In GitHub, open:
   `RP-SE-009 > Settings > Secrets and variables > Actions > New repository secret`
8. Add the secret:
   - Name: `SONAR_TOKEN`
   - Value: the SonarCloud project token
9. Open the **Actions** tab and manually run the `SonarCloud` workflow on `deployment-agent-dev`.

The workflow installs the backend and frontend dependencies, runs Python tests with coverage, builds the Next.js frontend, and sends the analysis to SonarCloud.

## 2. Connect Snyk

1. Sign in to Snyk using GitHub.
2. Import `Ravindu200232/RP-SE-009` into the required Snyk organization.
3. Open the Snyk account settings and copy the API token.
4. In GitHub, open:
   `RP-SE-009 > Settings > Secrets and variables > Actions > New repository secret`
5. Add the secret:
   - Name: `SNYK_TOKEN`
   - Value: the Snyk API token
6. In the Snyk organization settings, enable **Snyk Code** before running the source-code scan.
7. Open the GitHub **Actions** tab and manually run `Snyk Security` on `deployment-agent-dev`.

The Snyk workflow performs:

- Open-source dependency scanning for Python and Node.js
- Snyk Code source analysis
- Infrastructure-as-code scanning
- Snyk project monitoring after branch pushes
- A scheduled weekly scan

## Expected branch protection checks

After both workflows complete successfully, configure branch protection for `main` and require:

- `Build, test and analyze`
- `Dependency, code and IaC scan`

## Troubleshooting

### SonarCloud says project not found

The `sonar.organization` or `sonar.projectKey` value does not match the SonarCloud project. Copy the exact values from the SonarCloud project information page and update `sonar-project.properties`.

### SonarCloud says token is missing or invalid

Recreate the SonarCloud project token and replace the GitHub Actions secret named `SONAR_TOKEN`.

### Snyk authentication failed

Replace the GitHub Actions secret named `SNYK_TOKEN` with the current API token from Snyk account settings.

### Snyk Code is unavailable

Enable Snyk Code in the selected Snyk organization. If the plan does not include Snyk Code, remove or temporarily disable the `Test source code` step while keeping dependency and IaC scanning active.

### Pull requests from forks

GitHub does not pass repository secrets to untrusted fork pull requests. Security scans requiring tokens will only work for trusted branches or approved workflows.
