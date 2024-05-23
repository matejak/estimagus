/* 
  This is a Maxima batch file that can determine how to calculate
  PERT Optimistic/Pessimistic values from mean, variance, and mode

  a: Beta dist's Alpha shape parameter
  b: Beta dist's Beta shape parameter
  o: Beta Min value (and Pert Optimistic)
  p: Beta Max value (and Pert Pessimistic)
  m: Beta Mode (and PERT Most Likely)
  E: Beta Expected Value
  V: Beta Variance
  V: Pert Lambda (4 considered as "default")
 */

e1: (a * p + b * o) / (a + b) = E;
e2: (L * m + p + o) / (L + 2) = E;
e3: V = a * b * (p - o)^2 / (a + b)^2 / (a + b + 1);
e4: m = ((a - 1) * p + (b - 1) * o) / (a + b - 2);

s: algsys([e1, e2, e3, e4], [a, b, o, p]);

sol: first(s);

o: sol[3];
p: sol[4];
