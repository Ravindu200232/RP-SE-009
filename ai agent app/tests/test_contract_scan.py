from agents.repair.contract_scan import scan_text


def test_short_entity_callback_name_does_not_match_tails_of_other_identifiers():
    registry = {"Tea": {"fieldNames": ["name", "caffeineLevel"]}}
    source = """import type { Tea } from '@/types'
const teas: Tea[] = []
const filtered = teas.filter((t) => t.caffeineLevel === activeFilter)
React.useEffect(() => {}, [])
if (result.success) console.error(result.error)
"""
    assert scan_text("components/pages/Home.tsx", source, registry) == []


def test_typed_entity_callback_still_reports_a_real_unknown_field():
    registry = {"Tea": {"fieldNames": ["name"]}}
    source = """import type { Tea } from '@/types'
const teas: Tea[] = []
const labels = teas.map((t) => t.inventedFlavor)
"""
    findings = scan_text("components/pages/Home.tsx", source, registry)
    assert [(item["entity"], item["field"]) for item in findings] == [("Tea", "inventedFlavor")]
