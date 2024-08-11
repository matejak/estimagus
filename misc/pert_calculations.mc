/* 
  This is a Maxima batch file that can determine how to calculate
  PERT Optimistic/Pessimistic values from
  - mean, variance, and mode
  - mean, variance, and skewness (squared, to get rid of square roots)

  a: Beta dist's Alpha shape parameter
  b: Beta dist's Beta shape parameter
  o: Beta Min value (and Pert Optimistic)
  p: Beta Max value (and Pert Pessimistic)
  m: Beta Mode (and PERT Most Likely)
  S: Beta Skewness
  E: Beta Expected Value
  V: Beta Variance
  L: Pert Sigma (4 considered as "default")
 */

e1: (a * p + b * o) / (a + b) = E;
e2: (L * m + p + o) / (L + 2) = E;
e3: V = a * b * (p - o)^2 / (a + b)^2 / (a + b + 1);
e4: m = ((a - 1) * p + (b - 1) * o) / (a + b - 2);
e5: S^2 = 4 * (b - a)^2 * (a + b + 1) / (a * b) / (a + b + 2)^2;
e6: S = 2 * (b - a) * sqrt(a + b + 1) / sqrt(a * b) / (a + b + 2);


/* Given E, V, S and L, express o, p, m without involving a and b. */
s: algsys([e1, e2, e3, e4, e5], [a, b, o, p, m]);

/* There are multiple degenerate solutions, the fifth seems to be the right one */
sol: fifth(s);

display2d:false$
o_expr: sol[3];
p_expr: sol[4];
m_expr: sol[5];
