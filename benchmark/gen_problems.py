#!/usr/bin/env python3
"""Generate benchmark/problems.json — 100 graded theorems.

Tiers: trivial (20), easy (30), medium (30), hard (20).
All statements target `import Mathlib` + `open BigOperators Nat Finset`
(prepended automatically by the agent loop).

Regenerate: python benchmark/gen_problems.py
"""

import json
from pathlib import Path

SORRY = " := by\n  sorry"

P = []  # (id, difficulty, statement)


def add(pid: str, diff: str, stmt: str) -> None:
    P.append((pid, diff, stmt + SORRY))


# ---------------- trivial (20) ----------------
add("add_comm_nat", "trivial", "theorem add_comm_nat (a b : ℕ) : a + b = b + a")
add("mul_comm_nat", "trivial", "theorem mul_comm_nat (a b : ℕ) : a * b = b * a")
add("add_assoc_nat", "trivial", "theorem add_assoc_nat (a b c : ℕ) : a + b + c = a + (b + c)")
add("mul_assoc_nat", "trivial", "theorem mul_assoc_nat (a b c : ℕ) : a * b * c = a * (b * c)")
add("add_zero_nat", "trivial", "theorem add_zero_nat (a : ℕ) : a + 0 = a")
add("mul_one_nat", "trivial", "theorem mul_one_nat (a : ℕ) : a * 1 = a")
add("zero_mul_nat", "trivial", "theorem zero_mul_nat (a : ℕ) : 0 * a = 0")
add("nat_sub_self", "trivial", "theorem nat_sub_self (n : ℕ) : n - n = 0")
add("succ_injective", "trivial", "theorem succ_injective (a b : ℕ) : Nat.succ a = Nat.succ b → a = b")
add("add_right_cancel_nat", "trivial", "theorem add_right_cancel_nat (a b c : ℕ) : a + b = a + c → b = c")
add("mul_add_nat", "trivial", "theorem mul_add_nat (a b c : ℕ) : a * (b + c) = a * b + a * c")
add("sq_eq_mul", "trivial", "theorem sq_eq_mul (a : ℕ) : a ^ 2 = a * a")
add("two_mul_nat", "trivial", "theorem two_mul_nat (n : ℕ) : 2 * n = n + n")
add("nat_add_sub_cancel", "trivial", "theorem nat_add_sub_cancel (a b : ℕ) : a ≤ b → a + (b - a) = b")
add("int_add_neg_self", "trivial", "theorem int_add_neg_self (a : ℤ) : a + -a = 0")
add("int_neg_one_mul", "trivial", "theorem int_neg_one_mul (a : ℤ) : -1 * a = -a")
add("nat_le_succ", "trivial", "theorem nat_le_succ (n : ℕ) : n ≤ n + 1")
add("nat_lt_succ", "trivial", "theorem nat_lt_succ (n : ℕ) : n < n + 1")
add("prop_or_self", "trivial", "theorem prop_or_self (p : Prop) : p ∨ p ↔ p")
add("not_not_self_eq", "trivial", "theorem not_not_self_eq (a : ℕ) : ¬¬(a = a)")

# ---------------- easy (30) ----------------
add("sq_nonneg_int", "easy", "theorem sq_nonneg_int (x : ℤ) : 0 ≤ x ^ 2")
add("diff_of_squares", "easy", "theorem diff_of_squares (a b : ℤ) : a ^ 2 - b ^ 2 = (a - b) * (a + b)")
add("sum_sq_ge_prod", "easy", "theorem sum_sq_ge_prod (a b : ℤ) : 2 * a * b ≤ a ^ 2 + b ^ 2")
add("sq_add", "easy", "theorem sq_add (a b : ℤ) : (a + b) ^ 2 = a ^ 2 + 2 * a * b + b ^ 2")
add("cube_diff", "easy", "theorem cube_diff (a b : ℤ) : a ^ 3 - b ^ 3 = (a - b) * (a ^ 2 + a * b + b ^ 2)")
add("abs_le_iff", "easy", "theorem abs_le_iff (a b : ℤ) : |a| ≤ b ↔ -b ≤ a ∧ a ≤ b")
add("even_two_mul", "easy", "theorem even_two_mul (n : ℕ) : Even (2 * n)")
add("odd_succ_of_even", "easy", "theorem odd_succ_of_even (n : ℕ) : Even n → Odd (n + 1)")
add("even_add_even", "easy", "theorem even_add_even (a b : ℕ) : Even a → Even b → Even (a + b)")
add("even_mul_iff", "easy", "theorem even_mul_iff (a b : ℕ) : Even (a * b) ↔ Even a ∨ Even b")
add("even_sq_iff", "easy", "theorem even_sq_iff (n : ℕ) : Even (n ^ 2) ↔ Even n")
add("dvd_three_consecutive", "easy", "theorem dvd_three_consecutive (n : ℕ) : 3 ∣ n * (n + 1) * (n + 2)")
add("dvd_six_consecutive", "easy", "theorem dvd_six_consecutive (n : ℕ) : 6 ∣ n * (n + 1) * (n + 2)")
add("dvd_n_sq_add_n", "easy", "theorem dvd_n_sq_add_n (n : ℕ) : 2 ∣ n ^ 2 + n")
add("gcd_dvd_left", "easy", "theorem gcd_dvd_left (a b : ℕ) : Nat.gcd a b ∣ a")
add("gcd_dvd_right", "easy", "theorem gcd_dvd_right (a b : ℕ) : Nat.gcd a b ∣ b")
add("gcd_self", "easy", "theorem gcd_self (n : ℕ) : Nat.gcd n n = n")
add("gcd_zero_right", "easy", "theorem gcd_zero_right (n : ℕ) : Nat.gcd n 0 = n")
add("gcd_mul_lcm", "easy", "theorem gcd_mul_lcm (a b : ℕ) : Nat.gcd a b * Nat.lcm a b = a * b")
add("factorial_pos", "easy", "theorem factorial_pos (n : ℕ) : 0 < Nat.factorial n")
add("factorial_succ", "easy", "theorem factorial_succ (n : ℕ) : Nat.factorial (n + 1) = (n + 1) * Nat.factorial n")
add("choose_zero_right", "easy", "theorem choose_zero_right (n : ℕ) : Nat.choose n 0 = 1")
add("choose_self", "easy", "theorem choose_self (n : ℕ) : Nat.choose n n = 1")
add("choose_one_right", "easy", "theorem choose_one_right (n : ℕ) : Nat.choose n 1 = n")
add("two_mul_sum_range_id", "easy", "theorem two_mul_sum_range_id (n : ℕ) : 2 * (∑ i in range n, i) = n * (n - 1)")
add("sum_range_const", "easy", "theorem sum_range_const (n : ℕ) : (∑ i in range n, 1) = n")
add("card_range", "easy", "theorem card_range (n : ℕ) : (range n).card = n")
add("length_map", "easy", "theorem length_map {α β : Type _} (xs : List α) (f : α → β) : (xs.map f).length = xs.length")
add("length_append", "easy", "theorem length_append {α : Type _} (xs ys : List α) : (xs ++ ys).length = xs.length + ys.length")
add("reverse_reverse", "easy", "theorem reverse_reverse {α : Type _} (xs : List α) : xs.reverse.reverse = xs")

# ---------------- medium (30) ----------------
add("sum_first_n", "medium", "theorem sum_first_n (n : ℕ) : 2 * (∑ i in range (n + 1), i) = n * (n + 1)")
add("sum_sq_formula", "medium", "theorem sum_sq_formula (n : ℕ) : 6 * (∑ i in range (n + 1), i ^ 2) = n * (n + 1) * (2 * n + 1)")
add("sum_odd_eq_sq", "medium", "theorem sum_odd_eq_sq (n : ℕ) : (∑ i in range n, (2 * i + 1)) = n ^ 2")
add("geom_sum_mul", "medium", "theorem geom_sum_mul (x : ℤ) (n : ℕ) : (x - 1) * (∑ i in range n, x ^ i) = x ^ n - 1")
add("pow_dvd_pow", "medium", "theorem pow_dvd_pow (a b : ℕ) (n : ℕ) : a ∣ b → a ^ n ∣ b ^ n")
add("dvd_mul_of_dvd", "medium", "theorem dvd_mul_of_dvd (a b c : ℕ) : a ∣ b → a ∣ b * c")
add("dvd_add", "medium", "theorem dvd_add (a b c : ℕ) : a ∣ b → a ∣ c → a ∣ b + c")
add("dvd_sub_int", "medium", "theorem dvd_sub_int (a b c : ℤ) : a ∣ b → a ∣ c → a ∣ b - c")
add("gcd_mul_right", "medium", "theorem gcd_mul_right (a b c : ℕ) : Nat.gcd (a * c) (b * c) = c * Nat.gcd a b")
add("coprime_mul_right", "medium", "theorem coprime_mul_right (a b c : ℕ) : Nat.Coprime a b → Nat.Coprime a c → Nat.Coprime a (b * c)")
add("prime_dvd_mul", "medium", "theorem prime_dvd_mul (p a b : ℕ) : Nat.Prime p → p ∣ a * b → p ∣ a ∨ p ∣ b")
add("prime_not_dvd_one", "medium", "theorem prime_not_dvd_one (p : ℕ) : Nat.Prime p → ¬ p ∣ 1")
add("two_le_prime", "medium", "theorem two_le_prime (p : ℕ) : Nat.Prime p → 2 ≤ p")
add("prime_dvd_factorial", "medium", "theorem prime_dvd_factorial (p n : ℕ) : Nat.Prime p → p ≤ n → p ∣ Nat.factorial n")
add("factorial_dvd_factorial", "medium", "theorem factorial_dvd_factorial (m n : ℕ) : m ≤ n → Nat.factorial m ∣ Nat.factorial n")
add("choose_symm", "medium", "theorem choose_symm (n k : ℕ) : k ≤ n → Nat.choose n k = Nat.choose n (n - k)")
add("pascal_rule", "medium", "theorem pascal_rule (n k : ℕ) : Nat.choose (n + 1) (k + 1) = Nat.choose n k + Nat.choose n (k + 1)")
add("sum_choose_eq_two_pow", "medium", "theorem sum_choose_eq_two_pow (n : ℕ) : (∑ k in range (n + 1), Nat.choose n k) = 2 ^ n")
add("fib_add", "medium", "theorem fib_add (m n : ℕ) : Nat.fib (m + n + 1) = Nat.fib m * Nat.fib n + Nat.fib (m + 1) * Nat.fib (n + 1)")
add("fib_succ_succ", "medium", "theorem fib_succ_succ (n : ℕ) : Nat.fib (n + 2) = Nat.fib (n + 1) + Nat.fib n")
add("sq_abs", "medium", "theorem sq_abs (a : ℤ) : |a| ^ 2 = a ^ 2")
add("min_add_max", "medium", "theorem min_add_max (a b : ℕ) : min a b + max a b = a + b")
add("natAbs_mul", "medium", "theorem natAbs_mul (a b : ℤ) : Int.natAbs (a * b) = Int.natAbs a * Int.natAbs b")
add("dvd_antisymm", "medium", "theorem dvd_antisymm (a b : ℕ) : a ∣ b → b ∣ a → a = b")
add("bezout_nat", "medium", "theorem bezout_nat (a b : ℕ) : ∃ x y : ℤ, (a : ℤ) * x + (b : ℤ) * y = (Nat.gcd a b : ℤ)")
add("even_or_odd", "medium", "theorem even_or_odd (n : ℕ) : Even n ∨ Odd n")
add("not_even_and_odd", "medium", "theorem not_even_and_odd (n : ℕ) : ¬(Even n ∧ Odd n)")
add("odd_mul_odd", "medium", "theorem odd_mul_odd (a b : ℕ) : Odd a → Odd b → Odd (a * b)")
add("sq_mod_four", "medium", "theorem sq_mod_four (n : ℕ) : n ^ 2 % 4 = 0 ∨ n ^ 2 % 4 = 1")
add("mod_add_div", "medium", "theorem mod_add_div (a b : ℕ) : a % b + b * (a / b) = a")

# ---------------- hard (20) ----------------
add("sum_cubes_eq_sq_sum", "hard", "theorem sum_cubes_eq_sq_sum (n : ℕ) : (∑ i in range (n + 1), i) ^ 2 = ∑ i in range (n + 1), i ^ 3")
add("le_sqrt", "hard", "theorem le_sqrt (m n : ℕ) : n * n ≤ m → n ≤ Nat.sqrt m")
add("binomial_theorem_nat", "hard", "theorem binomial_theorem_nat (a b : ℕ) (n : ℕ) : (a + b) ^ n = ∑ k in range (n + 1), Nat.choose n k * a ^ k * b ^ (n - k)")
add("am_gm_two", "hard", "theorem am_gm_two (a b : ℕ) : 4 * a * b ≤ (a + b) ^ 2")
add("cauchy_schwarz_two_int", "hard", "theorem cauchy_schwarz_two_int (a b c d : ℤ) : (a * c + b * d) ^ 2 ≤ (a ^ 2 + b ^ 2) * (c ^ 2 + d ^ 2)")
add("dvd_thirty_n5_sub_n", "hard", "theorem dvd_thirty_n5_sub_n (n : ℤ) : 30 ∣ n ^ 5 - n")
add("dvd_six_n3_sub_n", "hard", "theorem dvd_six_n3_sub_n (n : ℤ) : 6 ∣ n ^ 3 - n")
add("dvd_seven_pow8_sub_1", "hard", "theorem dvd_seven_pow8_sub_1 (n : ℕ) : 7 ∣ 8 ^ n - 1")
add("dvd_three_pow4_sub_1", "hard", "theorem dvd_three_pow4_sub_1 (n : ℕ) : 3 ∣ 4 ^ n - 1")
add("dvd_eleven_pow10_sub_neg1", "hard", "theorem dvd_eleven_pow10_sub_neg1 (n : ℕ) : (11 : ℤ) ∣ (10 : ℤ) ^ n - (-1 : ℤ) ^ n")
add("fib_gcd", "hard", "theorem fib_gcd (m n : ℕ) : Nat.gcd (Nat.fib m) (Nat.fib n) = Nat.fib (Nat.gcd m n)")
add("choose_mul_factorial", "hard", "theorem choose_mul_factorial (n k : ℕ) : k ≤ n → Nat.choose n k * Nat.factorial k * Nat.factorial (n - k) = Nat.factorial n")
add("lt_two_pow_self", "hard", "theorem lt_two_pow_self (n : ℕ) : n < 2 ^ n")
add("factorial_lt_pow", "hard", "theorem factorial_lt_pow (n : ℕ) : 1 < n → Nat.factorial n < n ^ n")
add("bernoulli_nat", "hard", "theorem bernoulli_nat (x n : ℕ) : 1 + n * x ≤ (1 + x) ^ n")
add("exists_prime_dvd", "hard", "theorem exists_prime_dvd (n : ℕ) : 2 ≤ n → ∃ p, Nat.Prime p ∧ p ∣ n")
add("exists_prime_ge", "hard", "theorem exists_prime_ge (n : ℕ) : ∃ p, n ≤ p ∧ Nat.Prime p")
add("four_squares", "hard", "theorem four_squares (n : ℕ) : ∃ a b c d : ℕ, n = a ^ 2 + b ^ 2 + c ^ 2 + d ^ 2")
add("prime_sq_add_sq", "hard", "theorem prime_sq_add_sq (p : ℕ) : Nat.Prime p → p % 4 = 1 → ∃ a b : ℕ, p = a ^ 2 + b ^ 2")
add("prime_dvd_pow", "hard", "theorem prime_dvd_pow (p a : ℕ) (n : ℕ) : Nat.Prime p → p ∣ a ^ n → p ∣ a")


def main() -> None:
    assert len(P) == 100, f"expected 100 problems, got {len(P)}"
    ids = [p[0] for p in P]
    assert len(set(ids)) == 100, "duplicate ids"
    out = [
        {"id": pid, "difficulty": diff, "statement": stmt}
        for pid, diff, stmt in P
    ]
    dest = Path(__file__).parent / "problems.json"
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    counts = {}
    for _, d, _ in P:
        counts[d] = counts.get(d, 0) + 1
    print(f"wrote {dest} ({len(out)} problems: {counts})")


if __name__ == "__main__":
    main()
