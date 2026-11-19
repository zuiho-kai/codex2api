package proxy

import (
	"html"
	"testing"

	"github.com/codex2api/database"
)

// 2026-11 官网把已弃用型号写成 {label, deprecated} 对象，不能让整张表解析失败。
func TestOpenAIPricingIslandsDeprecatedLabelRows(t *testing.T) {
	props := `{"tier":[0,"standard"],"rows":[1,[` +
		`[1,[[0,"gpt-6.2-sol"],[0,2],[0,0.1],[0,2.5],[0,10]]],` +
		`[1,[[0,{"label":[0,"gpt-5.4-nano"],"deprecated":[0,true]}],[0,0.2],[0,0.02],[0,1.25]]]` +
		`]]}`
	body := []byte(`<html><body><astro-island component-export="TextTokenPricingTables" props="` + html.EscapeString(props) + `"></astro-island></body></html>`)
	out := map[string]database.ModelPricingOverride{}
	if err := openAIPricingIslands(body, out); err != nil {
		t.Fatal(err)
	}
	sol := out["gpt-6.2-sol"]
	if sol.Input != 2 || sol.CachedInput != 0.1 || sol.Output != 10 {
		t.Fatalf("gpt-6.2-sol = %+v", sol)
	}
	nano, ok := out["gpt-5.4-nano"]
	if !ok || nano.Input != 0.2 || nano.Output != 1.25 {
		t.Fatalf("gpt-5.4-nano = %+v ok=%v", nano, ok)
	}
}
