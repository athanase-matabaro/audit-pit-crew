# Audit-Pit-Crew: Configuration & Filtering System - Operational Guide

**Date**: November 29, 2025  
**Status**: ✅ PRODUCTION READY  
**Audience**: Development Team, DevOps, Security Team

---

## Quick Start

### For Repository Maintainers

#### 1. **Using Default Configuration** (Recommended for Most Projects)

No action needed! The system automatically:
- ✅ Scans your entire repository
- ✅ Excludes `node_modules/` and `test/` directories
- ✅ Reports all severity levels (Low and above)

**Example**: If your Solidity contracts are in the root or any subdirectory, they'll be scanned automatically.

#### 2. **Customizing for Your Project**

Create `audit-pit-crew.yml` in your repository root:

```yaml
scan:
  contracts_path: "."                    # Or specific subdirectory
  ignore_paths:
    - "node_modules/**"
    - "test/**"
  min_severity: "Medium"                 # or "High", "Critical"
```

**Effect**: Changes take effect immediately on next PR or push.

#### 3. **Common Configurations**

##### **Enterprise Security Policy (Strict)**
```yaml
scan:
  contracts_path: "contracts"
  ignore_paths:
    - "node_modules/**"
    - "test/**"
    - "deprecated/**"
    - "**/external/**"
  min_severity: "High"
```

##### **Development Project (Comprehensive)**
```yaml
scan:
  contracts_path: "src/contracts"
  ignore_paths:
    - "node_modules/**"
    - "test/**"
  min_severity: "Low"
```

##### **Audit Scenario (Everything)**
```yaml
scan:
  contracts_path: "."
  ignore_paths: []                       # Scan everything
  min_severity: "Low"                    # Report all issues
```

---

## System Architecture

### How It Works

```
1. Repository Pushed/PR Created
   ↓
2. Webhook Received by API
   ↓
3. Configuration Loaded (audit-pit-crew.yml)
   ↓
4. Git Diff → Identify Changed Files
   ↓
5. Apply Config Filters
   ├─ Filter by contracts_path
   ├─ Filter by ignore_paths patterns
   └─ Result: Filtered file list
   ↓
6. Run Scanners (Slither + Mythril)
   ├─ Slither: Static analysis
   └─ Mythril: EVM bytecode analysis
   ↓
7. Aggregate Results
   ├─ Apply min_severity filter
   └─ Deduplicate issues
   ↓
8. Post Report to GitHub
   └─ PR comment with findings
```

---

## Configuration Reference

### `contracts_path`

Specifies which directory contains your Solidity contracts.

| Value | Behavior | Example |
|-------|----------|---------|
| `"."` | Scan entire repository | All .sol files anywhere |
| `"contracts"` | Scan specific directory | Only `contracts/**/*.sol` |
| `"src/contracts"` | Nested directory | Only `src/contracts/**/*.sol` |

**Default**: `"."`

**Impact**: Reduces scanning scope, speeds up analysis

### `ignore_paths`

Glob patterns for directories/files to exclude from scanning.

| Pattern | Matches |
|---------|---------|
| `"node_modules/**"` | Everything in node_modules/ |
| `"test/**"` | Everything in test/ |
| `"**/vendor/**"` | vendor/ anywhere in tree |
| `"contracts/external/**"` | External code in contracts/ |
| `"**/mocks/*"` | Mock files anywhere |

**Default**: `["node_modules/**", "test/**"]`

**Impact**: Prevents false positives from third-party code

### `min_severity`

Minimum severity level to report.

| Level | Includes | Excludes |
|-------|----------|----------|
| `"Low"` | Low, Medium, High, Critical | None |
| `"Medium"` | Medium, High, Critical | Low |
| `"High"` | High, Critical | Low, Medium |
| `"Critical"` | Critical only | Low, Medium, High |

**Default**: `"Low"`

**Impact**: Focus on important issues, reduce noise

---

## Monitoring & Debugging

### View Configuration Status

Check Docker logs to see which configuration was loaded:

```bash
# View worker logs
docker logs audit_pit_worker | grep "Configuration"

# Example output:
# ✅ Configuration loaded successfully. Contracts path: ., Min severity: Low, ...
# ℹ️ Config file not found at [...]. Using default configuration.
```

### Verify File Filtering

Look for these log messages:

```
📋 Using contracts_path: contracts
✅ Found 5 changed Solidity files after applying config filters
```

**Meaning**: 
- Config is loaded
- Files matching criteria were identified

### Check Issue Filtering

Look for these log messages:

```
🎯 Slither: Filtering issues with minimum severity: Medium
Slither found 2 total issues meeting the severity threshold
```

**Meaning**:
- Severity filter was applied
- Only medium/high/critical issues reported

---

## Troubleshooting

### Configuration Not Being Used

**Symptom**: System uses defaults despite configuration file

**Check**:
1. File name exactly: `audit-pit-crew.yml` (lowercase, exact spelling)
2. File location: Repository root (same level as .git folder)
3. YAML syntax: No tabs, proper indentation

**Verify**:
```bash
# File should exist at repository root
ls -la audit-pit-crew.yml

# Should not error
python3 -c "import yaml; yaml.safe_load(open('audit-pit-crew.yml'))"
```

**Fix**: Correct file name/location, validate YAML syntax

### Too Many Issues Reported

**Symptom**: Report includes too many issues

**Check**:
1. Verify `min_severity` setting
2. Check `ignore_paths` includes all test directories

**Fix**:
```yaml
scan:
  min_severity: "Medium"                 # Be more strict
  ignore_paths:
    - "node_modules/**"
    - "test/**"
    - "tests/**"                         # Add if missing
```

### Too Few Issues Reported

**Symptom**: Report missing expected issues

**Check**:
1. Verify `min_severity` is not too strict
2. Check `contracts_path` includes target directory
3. Verify file is in diff (actually changed)

**Fix**:
```yaml
scan:
  contracts_path: "."                    # Include all directories
  min_severity: "Low"                    # Report all levels
```

### No Files Scanned

**Symptom**: "No target files changed" message

**Check**:
1. Verify files are .sol files
2. Verify files are in `contracts_path`
3. Verify files are not in `ignore_paths`

**Fix**: Adjust configuration to include target files

---

## Examples by Project Type

### DeFi Protocol

```yaml
scan:
  contracts_path: "contracts"
  ignore_paths:
    - "contracts/test/**"
    - "contracts/mocks/**"
    - "node_modules/**"
  min_severity: "High"
```

**Rationale**: Strict security policy for financial protocol

### NFT Project

```yaml
scan:
  contracts_path: "src/contracts"
  ignore_paths:
    - "src/contracts/external/**"
    - "node_modules/**"
    - "test/**"
  min_severity: "Medium"
```

**Rationale**: Medium focus for NFT-specific contracts

### Tool/Utility

```yaml
scan:
  contracts_path: "."
  ignore_paths:
    - "node_modules/**"
  min_severity: "Low"
```

**Rationale**: Comprehensive scanning for tools

### Governance Token

```yaml
scan:
  contracts_path: "contracts"
  ignore_paths:
    - "contracts/vendor/**"
    - "test/**"
  min_severity: "Critical"
```

**Rationale**: Focus only on critical issues for tokens

---

## Performance Tips

### 1. **Narrow contracts_path**

❌ Slow:
```yaml
contracts_path: "."
```

✅ Fast:
```yaml
contracts_path: "src/contracts"
```

**Impact**: 2-3x faster for large monorepos

### 2. **Expand ignore_paths**

❌ Slow:
```yaml
ignore_paths: []
```

✅ Fast:
```yaml
ignore_paths:
  - "node_modules/**"
  - "test/**"
  - "vendor/**"
```

**Impact**: Skips unnecessary files

### 3. **Use Higher min_severity**

❌ Slow:
```yaml
min_severity: "Low"
```

✅ Fast:
```yaml
min_severity: "High"
```

**Impact**: Processes fewer issues (post-scan, minimal effect)

---

## Operational Checklist

### Before Production Deployment

- [ ] Create `audit-pit-crew.yml` or verify defaults are acceptable
- [ ] Test with a draft PR
- [ ] Verify configuration is loaded (check logs)
- [ ] Verify files are filtered correctly
- [ ] Verify report appears on PR
- [ ] Review reported issues for accuracy

### For Maintenance

- [ ] Monitor Docker logs weekly
- [ ] Review issue reports for accuracy
- [ ] Adjust configuration based on team feedback
- [ ] Document any custom configurations in team wiki

### For Security Reviews

- [ ] Verify configuration matches security policy
- [ ] Ensure `min_severity` aligns with risk tolerance
- [ ] Review `ignore_paths` for completeness
- [ ] Audit configuration changes in git history

---

## Best Practices

### ✅ DO

- **Keep configuration in git** - Version control your security settings
- **Use version control for audit-pit-crew.yml** - Track changes
- **Start with defaults** - Then customize based on needs
- **Review reported issues** - Trust the tools but verify results
- **Update ignore patterns** - Keep vendor/external code excluded
- **Monitor logs** - Catch configuration issues early

### ❌ DON'T

- **Ignore High/Critical issues** - Always review findings
- **Set min_severity to Critical only** - You'll miss important bugs
- **Change configuration without testing** - Verify with a PR first
- **Commit test files to production** - Keep test code in test/ directory
- **Scan vendor dependencies** - Use ignore_paths to exclude them
- **Leave configuration out of git** - You'll lose reproducibility

---

## Support & Escalation

### Issue: Configuration Error

1. Validate YAML syntax
2. Check file name/location
3. Review logs for error messages
4. Refer to configuration reference

### Issue: Unexpected Filtering

1. Check `contracts_path` setting
2. Review `ignore_paths` patterns
3. Verify file matches criteria
4. Test with simpler configuration

### Issue: Unexpected Issues Reported

1. Verify `min_severity` setting
2. Check ignore patterns
3. Review actual file for vulnerabilities
4. Verify Slither/Mythril configuration

### Issue: Performance Problems

1. Narrow `contracts_path`
2. Expand `ignore_paths`
3. Increase `min_severity`
4. Check repository size

---

## Contact & Resources

### Documentation

- **Main Docs**: `docs/` folder in repository
- **Configuration Examples**: `docs/CONFIGURATION_EXAMPLES.md`
- **Full Verification**: `docs/SYSTEM_UPDATE_VERIFICATION.md`
- **Quick Reference**: `docs/QUICK_REFERENCE.md`

### Git Repository

- **Configuration File**: `audit-pit-crew.yml.example` (template)
- **Docker Setup**: `docker-compose.yml`
- **Task Definition**: `src/worker/tasks.py`

---

## Glossary

| Term | Definition |
|------|-----------|
| **Configuration** | `audit-pit-crew.yml` file with scanning rules |
| **Contracts Path** | Directory containing Solidity contracts |
| **Ignore Paths** | Glob patterns for directories to exclude |
| **Min Severity** | Minimum issue severity to report |
| **Deduplication** | Removing duplicate issues from multiple tools |
| **Tool** | Security analysis tool (Slither or Mythril) |
| **Scan** | Complete analysis of repository/PR |
| **Filtering** | Selecting subset of files or issues |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-11-29 | Initial release with configuration system |

---

## Document Sign-Off

**Status**: ✅ APPROVED FOR PRODUCTION  
**Last Updated**: November 29, 2025  
**Next Review**: December 29, 2025

---

*This operational guide provides all necessary information for team members to configure, deploy, and maintain the audit-pit-crew security scanning system in production.*

