package proxy

import "testing"

// OpenAI 2026-11 起调整了价格表列顺序（output 在 cached input 前，新增 30m/12h 写入列）。
func TestParseOpenAIOfficialPricingMarkdownReorderedColumns(t *testing.T) {
	body := []byte(`### Standard pricing data

| Model | Short context input | Short context output | Short context cached input | Short context 30m write | Short context 12h write | Long context input | Long context output | Long context cached input | Long context 30m write | Long context 12h write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-6.2-sol | $2.00 | $10.00 | $0.10 | $2.50 | $5.00 | $4.00 | $15.00 | $0.20 | $5.00 | $10.00 |

### Batch pricing data

| Model | Short context input | Short context output | Short context cached input | Short context 30m write | Short context 12h write | Long context input | Long context output | Long context cached input | Long context 30m write | Long context 12h write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-6.2-sol | $1.00 | $5.00 | $0.05 | $1.25 | $2.50 | $2.00 | $7.50 | $0.10 | $2.50 | $5.00 |

### Fast pricing data

| Model | Short context input | Short context output | Short context cached input | Short context 30m write | Short context 12h write | Long context input | Long context output | Long context cached input | Long context 30m write | Long context 12h write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-6.2-sol | $4.00 | $20.00 | $0.20 | $5.00 | $10.00 | $8.00 | $30.00 | $0.40 | $10.00 | $20.00 |
`)
	got, err := ParseOpenAIOfficialPricingMarkdown(body)
	if err != nil {
		t.Fatal(err)
	}
	p, ok := got["gpt-6.2-sol"]
	if !ok {
		t.Fatalf("gpt-6.2-sol missing: %v", got)
	}
	checks := map[string][2]float64{
		"input": {p.Input, 2}, "cached": {p.CachedInput, 0.1}, "output": {p.Output, 10},
		"input_long": {p.InputLong, 4}, "cached_long": {p.CachedInputLong, 0.2}, "output_long": {p.OutputLong, 15},
		"input_fast": {p.InputPriority, 4}, "cached_fast": {p.CachedInputPriority, 0.2}, "output_fast": {p.OutputPriority, 20},
		"output_long_fast": {p.OutputLongPriority, 30},
	}
	for name, c := range checks {
		if c[0] != c[1] {
			t.Errorf("%s = %v, want %v", name, c[0], c[1])
		}
	}
}
