# Review audit index

This companion to the revised paper locates checks in the **unchanged frozen**
mathematical sources. Source hashes are in `CHECKER-FREEZE.json`; exact ranges
and guard fragments are also in [rule-obligation-index.json](rule-obligation-index.json).
The listed tests are related targeted regressions; they do not claim isolated coverage
of every guard and do not replace complete-certificate verification.

## Long-rule and coverage checks

| Obligation | Frozen function and lines | Related rejection test |
| --- | --- | --- |
| All accepted nodes, including terminals, obey p <= H; White has not won | [`reference_gap_verifier.py:303-307`](../scripts/reference_gap_verifier.py#L303) `verify` | `test_terminal_is_subject_to_total_budget`<br>`test_white_five_cannot_hide_behind_black_terminal` |
| Black and retained White actions require every reconstructed outcome | [`reference_gap_verifier.py:330-382`](../scripts/reference_gap_verifier.py#L330) `verify` | `test_missing_black_outcome_is_rejected`<br>`test_missing_retained_white_outcome_is_rejected` |
| Local suffix exclusion: both counterfour points avoid all current/later requirements | [`reference_infinite_threat_witness.py:112-130`](../scripts/reference_infinite_threat_witness.py#L112) `verify` | Source-level obligation; no isolated test claimed |
| Complete local counterfour closure; exactly one White completion | [`reference_infinite_threat_witness.py:114-130`](../scripts/reference_infinite_threat_witness.py#L114) `verify` | `test_white_double_counterfour_rejects_local_attack` |
| Local clock counts gain, one actual defense and two moves per counterfour | [`reference_infinite_threat_witness.py:105-141`](../scripts/reference_infinite_threat_witness.py#L105) `verify` | `test_prepared_clock_and_missing_remote_blocker` |
| Local remote envelopes, future footprint exclusion and mixed-line guard | [`reference_infinite_threat_witness.py:143-187`](../scripts/reference_infinite_threat_witness.py#L143) `verify` | Source-level obligation; no isolated test claimed |
| Prepared rule reconstructs all recorded local states and the complete footprint | [`reference_prepared_remote_sequence.py:48-86`](../scripts/reference_prepared_remote_sequence.py#L48) `record_closure` | `test_prepared_mixed_remote_local_triple` |
| Prepared rule delegates suffix, closure and local clock to frozen local checker | [`reference_prepared_remote_sequence.py:165-166`](../scripts/reference_prepared_remote_sequence.py#L165) `verify` | `test_prepared_clock_and_missing_remote_blocker` |
| Prepared pure remote blockers, envelope separation and all recorded mixed lines | [`reference_prepared_remote_sequence.py:168-178`](../scripts/reference_prepared_remote_sequence.py#L168) `verify` | `test_prepared_clock_and_missing_remote_blocker`<br>`test_prepared_mixed_remote_local_triple` |
| Remote graph is complete; before-block and after-block states are recorded | [`reference_remote_interruption_sequence.py:14-44`](../scripts/reference_remote_interruption_sequence.py#L14) `remote_audit` | `test_remote_unsealed_three_and_initial_four` |
| Remote Black block making five stops the remote graph; bounds include that block | [`reference_remote_interruption_sequence.py:23-41`](../scripts/reference_remote_interruption_sequence.py#L23) `remote_audit` | `test_remote_clock_counts_both_actual_moves` |
| Reserve twice the sum of all remote maxima before checking local witness | [`reference_remote_interruption_sequence.py:76-79`](../scripts/reference_remote_interruption_sequence.py#L76) `verify` | `test_remote_clock_counts_both_actual_moves` |
| Multiple frames: future activity separation, statewise maximum mixed contributions | [`reference_remote_interruption_sequence.py:88-105`](../scripts/reference_remote_interruption_sequence.py#L88) `verify.separated` | `test_future_remote_block_collides_with_local_suffix`<br>`test_two_remote_frames_cannot_hide_mixed_triple` |
| Final total L + 2 sum N_j fits H - p | [`reference_remote_interruption_sequence.py:104-112`](../scripts/reference_remote_interruption_sequence.py#L104) `verify` | `test_remote_clock_counts_both_actual_moves` |
| Twenty roots and all 120 first replies; only origin-fixing lattice isometries | [`reference_gap_opening_cover.py:18-52`](../scripts/reference_gap_opening_cover.py#L18) `validate_header` | `test_missing_duplicate_and_wrong_opening_frame` |

Local `I.verify` is deliberately conservative: a counterfour Black block that already
wins can still be subjected to later closure checks. This may reject a sound strategy;
it cannot validate an unsound one. `R.remote_audit` explicitly stops at a Black five.
No mathematics or acceptance predicate was changed in this revision.

## Executable rejection regressions

From the repository root, with assertions enabled:

```text
python -B test_certificate_rejection.py
```

Expected: all 19 named tests pass and the process exits zero. The suite imports only
frozen independent kernels and the standard library; no search engine or primary
`src` module is needed. Small fixtures and their original-byte identities are in
[fixture-bindings.json](fixture-bindings.json). The empty-cover fixture is used only
to test its first-reply header, without reading its certificate dependencies.

| Named test | Audit purpose |
| --- | --- |
| `test_disabled_assertions_are_refused` | An optimized Python runtime cannot silently skip checks. |
| `test_fixture_controls_are_accepted` | Unmutated small controls pass the same kernels. |
| `test_frozen_kernel_identities` | All eight source identities match the freeze. |
| `test_future_remote_block_collides_with_local_suffix` | Future remote block colliding with the local footprint is rejected. |
| `test_missing_black_outcome_is_rejected` | Missing universal Black outcome is rejected. |
| `test_missing_duplicate_and_wrong_opening_frame` | Missing/duplicate first replies and nonisometric transforms are rejected. |
| `test_missing_retained_white_outcome_is_rejected` | Missing retained White continuation is rejected. |
| `test_occupied_black_move_is_rejected` | Illegal occupied Black action is rejected. |
| `test_prepared_clock_and_missing_remote_blocker` | Prepared rule needs both its full clock and the actual remote blockers. |
| `test_prepared_mixed_remote_local_triple` | A mixed triple is rejected although isolated local reasoning is insufficient. |
| `test_relative_black_action_preserves_all_gap_outcomes` | Both near and far outcomes of one relative Black action remain required. |
| `test_remote_clock_counts_both_actual_moves` | An interruption needs the White move plus the Black block. |
| `test_remote_unsealed_three_and_initial_four` | Double remote counterfour and an initial immediate White threat are rejected. |
| `test_terminal_is_subject_to_total_budget` | Even a genuine Black terminal is rejected when p exceeds H. |
| `test_two_remote_frames_cannot_hide_mixed_triple` | Mixed threats across two individually separated frames are rejected. |
| `test_white_double_counterfour_rejects_local_attack` | Two White completion points invalidate a supposed unique counterfour. |
| `test_white_five_cannot_hide_behind_black_terminal` | A remote White five cannot be hidden by a Black terminal label. |
| `test_white_immediate_win_and_malformed_pattern_reject` | Immediate White win and altered threat signature are rejected. |
| `test_wrong_turn_type_anchor_and_duplicate_stone` | Wrong turn, noninteger budget, Boolean anchor and duplicate stones are rejected. |
