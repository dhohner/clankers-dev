# Negative Control

Keep a medium-confidence fix only when its targeted test fails under this negative control:

1. Record the edited file's `git hash-object` value.
2. Break the fixed lines on purpose with a small behavior change, such as an inverted condition or a changed return value.
3. Run the targeted test and confirm that it fails.
4. Restore the file and confirm that `git hash-object` prints the recorded value.

Reverse the fix with a `validation` reason when the test still passes with the break in place.
Record the deliberate break and the failing test for the report's `Negative control` line.

The negative control is complete when the file matches the recorded hash and the fix is either kept with a failing test or reversed.
