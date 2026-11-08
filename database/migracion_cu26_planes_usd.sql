UPDATE plan
SET moneda = 'USD', revision = revision + 1
WHERE codigo IN ('BASICO', 'INTERMEDIO', 'PREMIUM')
  AND moneda = 'BOB'
  AND precio = 0
  AND stripe_price_id IS NULL;
