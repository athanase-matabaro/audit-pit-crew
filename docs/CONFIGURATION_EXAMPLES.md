# Configuration Examples and Use Cases

## Example 1: Standard Configuration

```yaml
# audit-pit-crew.yml
scan:
  contracts_path: "contracts/"
  ignore_paths:
    - "node_modules/**"
    - "test/**"
  min_severity: "Medium"
```

**Behavior**:
- Only scans files under `contracts/` directory
- Excludes NPM modules and test files
- Reports only Medium, High, and Critical issues
- Ignores Low and Informational issues

---

## Example 2: Monorepo with Multiple Contracts

```yaml
# audit-pit-crew.yml
scan:
  contracts_path: "packages/smart-contracts/"
  ignore_paths:
    - "node_modules/**"
    - "test/**"
    - "dist/**"
    - "*.mock.sol"
  min_severity: "High"
```

**Behavior**:
- Only scans `packages/smart-contracts/` directory
- Excludes build outputs and mock files
- Reports only High and Critical issues
- Ideal for production contracts in monorepo

---

## Example 3: Development Configuration (Permissive)

```yaml
# audit-pit-crew.yml
scan:
  contracts_path: "./"
  ignore_paths:
    - ".git/**"
  min_severity: "Low"
```

**Behavior**:
- Scans entire repository (all Solidity files)
- Excludes only git metadata
- Reports all issues (Low and above)
- Useful during active development

---

## Example 4: Strict Configuration (Production-Ready)

```yaml
# audit-pit-crew.yml
scan:
  contracts_path: "src/contracts/"
  ignore_paths:
    - "node_modules/**"
    - "test/**"
    - "dist/**"
    - "build/**"
    - "**/*.mock.sol"
    - "**/*.test.sol"
  min_severity: "Critical"
```

**Behavior**:
- Very restrictive path (src/contracts/)
- Excludes comprehensive list of non-production files
- Reports only Critical issues
- Ideal for mainnet contracts

---

## Example 5: Default Configuration (No File)

```yaml
# Implicit default when audit-pit-crew.yml is not present
scan:
  contracts_path: "."
  ignore_paths:
    - "node_modules/**"
    - "test/**"
  min_severity: "Low"
```

**Behavior**:
- Scans entire repository
- Excludes common development artifacts
- Reports all detected issues
- Suitable for baseline scans

---

## Configuration Changes During PR

### Scenario: Lowering Severity Threshold

**Previous Configuration** (in main branch):
```yaml
min_severity: "High"
```

**New Configuration** (in PR):
```yaml
min_severity: "Medium"
```

**Result**:
- PR scan will report Medium, High, and Critical issues
- More thorough review of changes
- Better detection of potential issues

### Scenario: Expanding Scan Scope

**Previous Configuration**:
```yaml
contracts_path: "contracts/production/"
```

**New Configuration**:
```yaml
contracts_path: "contracts/"
```

**Result**:
- PR will now scan all contracts (including staging)
- More comprehensive coverage
- May increase noise if staging contracts have issues

---

## Error Handling Examples

### Example 1: Malformed YAML

```yaml
# Invalid YAML - missing colon
scan
  contracts_path: "contracts/"
```

**Result**: 
- System logs: "❌ Failed to parse YAML config file: ..."
- Falls back to default configuration
- Scan continues normally

### Example 2: Invalid Severity Value

```yaml
scan:
  contracts_path: "contracts/"
  min_severity: "InvalidLevel"  # Not one of: Low, Medium, High, Critical
```

**Result**:
- System logs: "❌ Configuration validation failed: ..."
- Falls back to default configuration (min_severity: "Low")
- Scan continues with Low threshold

### Example 3: Invalid Path Type

```yaml
scan:
  contracts_path: 123  # Should be string
```

**Result**:
- System logs: "❌ Configuration validation failed: ..."
- Falls back to default configuration
- Scan continues with root directory

### Example 4: Missing Configuration File

```
# No audit-pit-crew.yml in repository
```

**Result**:
- System logs: "ℹ️ Config file not found. Using default configuration."
- Uses default configuration
- Scan proceeds normally

---

## Migration Guide

### Adding Configuration to Existing Project

**Step 1**: Create `audit-pit-crew.yml` in repository root

```yaml
scan:
  contracts_path: "contracts/"
  ignore_paths:
    - "node_modules/**"
    - "test/**"
  min_severity: "Medium"
```

**Step 2**: Commit and push to repository

**Step 3**: Next PR will automatically use new configuration

**Result**: 
- Existing baselines may change due to filtering
- May need to update GitHub issue reports
- Ensure team is aware of new filtering rules

### Updating Configuration

1. Edit `audit-pit-crew.yml` in PR
2. New scan will use updated configuration
3. Different results compared to main branch
4. PR will show filtered issues only

---

## Performance Impact Examples

### Large Repository with Default Config
- Total changed files: 50
- After contracts_path filter: 50 (no change, scans root)
- After ignore_paths filter: 45 (5 from node_modules)
- Final scan: 45 files

### Monorepo with Restrictive Config
- Total changed files: 100
- After contracts_path filter: 15 (only "packages/contracts/")
- After ignore_paths filter: 10 (5 test files)
- Final scan: 10 files
- **Result**: 90% reduction in scan scope

### Issue Filtering Impact
- Issues found by Slither: 25
- After min_severity filter (High): 8 issues
- **Result**: 68% reduction in reported issues

---

## Common Mistakes to Avoid

❌ **Mistake 1**: Using Windows path separators
```yaml
contracts_path: "contracts\src"  # Wrong on Unix/Linux
```
✅ **Correct**:
```yaml
contracts_path: "contracts/src"  # Use forward slashes
```

❌ **Mistake 2**: Using absolute paths
```yaml
contracts_path: "/absolute/path/contracts"  # Wrong
```
✅ **Correct**:
```yaml
contracts_path: "contracts/"  # Relative to repo root
```

❌ **Mistake 3**: Missing trailing slashes in glob patterns
```yaml
ignore_paths:
  - "node_modules"  # May not match all files
```
✅ **Correct**:
```yaml
ignore_paths:
  - "node_modules/**"  # Matches all nested files
```

❌ **Mistake 4**: Case sensitivity in ignore patterns
```yaml
ignore_paths:
  - "Test/**"  # May not match "test/" on case-sensitive systems
```
✅ **Correct**:
```yaml
ignore_paths:
  - "test/**"
  - "Test/**"  # Or use lowercase and ensure consistency
```

---

## Troubleshooting

### Configuration Not Being Applied

**Check**:
1. Is `audit-pit-crew.yml` in repository root?
2. Is the YAML syntax valid?
3. Check task logs for configuration loading messages

**Solution**:
- Verify file location: repository root only
- Validate YAML using online validator
- Check logs: "📖 Loading configuration from..."

### Too Many Files Being Scanned

**Check**:
1. Is `contracts_path` correct?
2. Are `ignore_paths` patterns working?

**Solution**:
- Test glob patterns: `python -m fnmatch "path/to/file" "pattern"`
- Add more specific ignore patterns
- Consider reducing `contracts_path` scope

### Not Enough Issues Reported

**Check**:
1. Is `min_severity` set too high?
2. Are issues being filtered unintentionally?

**Solution**:
- Lower `min_severity` to "Low" for testing
- Check logs for filtered-out issues
- Verify severity mapping

### Configuration Reverted After Update

**Note**: Configuration must be committed and pushed to main branch to persist across scans

**Solution**:
1. Commit `audit-pit-crew.yml` to git
2. Push to repository
3. Wait for changes to propagate
