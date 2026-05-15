"""
app/ml/explainer.py
────────────────────
Generates human-readable explanations for lead scores.
Two-layer explanation: VALUE signals (business potential) and
CONFIDENCE signals (data quality / verification).
"""
from typing import Dict, List


def generate_explanation(
    signals: Dict[str, float],
    value_score: float,
    confidence_score: float,
    signal_score: float,
    ml_reply: float,
    ml_conversion: float,
    lead_data: dict | None = None,
) -> Dict[str, any]:
    """
    Build structured human-readable explanations, grouped by VALUE and CONFIDENCE.
    """
    value_factors: List[str] = []
    confidence_factors: List[str] = []
    top_reasons: List[str] = []
    lead = lead_data or {}

    # ═════════════════════════════════════════════════════════════════════
    # VALUE SIGNALS — Business potential
    # ═════════════════════════════════════════════════════════════════════
    if signals.get("is_decision_maker", 0) >= 1.0:
        title = lead.get("title", "Unknown")
        msg = f"✅ Decision-maker role identified: {title}"
        value_factors.append(msg)
        top_reasons.append(msg)
    else:
        if lead.get("title"):
            value_factors.append(f"ℹ️ Non-decision-maker role: {lead['title']}")
        else:
            value_factors.append("⚠️ No job title provided — unable to assess seniority")

    ts = signals.get("title_score", 0)
    if ts >= 0.8:
        value_factors.append(f"✅ High seniority title score ({ts:.2f}) — strong buying authority")
    elif ts >= 0.5:
        value_factors.append(f"ℹ️ Mid-level title score ({ts:.2f}) — moderate influence")
    elif ts > 0:
        value_factors.append(f"⚠️ Junior title score ({ts:.2f}) — limited decision power")

    eng = signals.get("engagement_score", 0)
    if eng >= 0.7:
        msg = f"✅ High engagement ({eng:.2f}) — strong interaction signals"
        value_factors.append(msg)
        if len(top_reasons) < 3: top_reasons.append(msg)
    elif eng >= 0.4:
        value_factors.append(f"ℹ️ Moderate engagement ({eng:.2f})")
    else:
        value_factors.append(f"⚠️ Low engagement ({eng:.2f}) — limited interaction history")

    if signals.get("has_company", 0) >= 1.0:
        company = lead.get("company", "")
        value_factors.append(f"✅ Company identified: {company}" if company else "✅ Company name present")
    else:
        value_factors.append("⚠️ No company information — harder to personalise outreach")

    if signals.get("is_referral", 0) >= 1.0:
        msg = "✅ Referral source — highest trust acquisition channel"
        value_factors.append(msg)
        if len(top_reasons) < 3: top_reasons.append(msg)

    if ml_reply >= 0.7:
        msg = f"✅ High ML reply probability ({ml_reply:.2f}) — likely to respond"
        value_factors.append(msg)
        if len(top_reasons) < 3 and ml_reply >= 0.85: top_reasons.append(msg)
    elif ml_reply >= 0.4:
        value_factors.append(f"ℹ️ Moderate ML reply probability ({ml_reply:.2f})")
    else:
        value_factors.append(f"⚠️ Low ML reply probability ({ml_reply:.2f})")

    if ml_conversion >= 0.7:
        value_factors.append(f"✅ High ML conversion probability ({ml_conversion:.2f}) — strong revenue potential")
    elif ml_conversion >= 0.4:
        value_factors.append(f"ℹ️ Moderate ML conversion probability ({ml_conversion:.2f})")
    else:
        value_factors.append(f"⚠️ Low ML conversion probability ({ml_conversion:.2f})")

    if value_score >= 0.7:
        value_factors.append(f"📊 Value Score: {value_score:.2f} — HIGH business potential")
    elif value_score >= 0.4:
        value_factors.append(f"📊 Value Score: {value_score:.2f} — MODERATE business potential")
    else:
        value_factors.append(f"📊 Value Score: {value_score:.2f} — LOW business potential")

    # ═════════════════════════════════════════════════════════════════════
    # CONFIDENCE SIGNALS — Data quality / verification
    # ═════════════════════════════════════════════════════════════════════
    nq = signals.get("name_quality", 0)
    if nq >= 0.8:
        confidence_factors.append("✅ Strong name quality — first and last name present")
    elif nq >= 0.5:
        confidence_factors.append("ℹ️ Partial name information — moderate data quality")
    elif nq > 0:
        confidence_factors.append("⚠️ Weak name data — possible placeholder or incomplete record")
    else:
        confidence_factors.append("⚠️ No name data — data quality concern")

    if signals.get("has_linkedin", 0) >= 1.0:
        msg = "✅ LinkedIn profile available — verified professional identity"
        confidence_factors.append(msg)
        if len(top_reasons) < 3: top_reasons.append(msg)
    else:
        confidence_factors.append("ℹ️ No LinkedIn profile — lower verification level")

    if signals.get("is_business_email", 0) >= 1.0:
        domain = ""
        email = lead.get("email", "")
        if email and "@" in email:
            domain = email.split("@")[-1]
        msg = f"✅ Business email ({domain}) — higher trust signal" if domain else "✅ Business email detected"
        confidence_factors.append(msg)
        if len(top_reasons) < 3: top_reasons.append(msg)
    else:
        confidence_factors.append("ℹ️ Personal/free email — not penalised, treated as weak confidence signal")

    eds = signals.get("email_domain_score", 0)
    if eds >= 0.8:
        confidence_factors.append(f"✅ Premium email domain ({eds:.2f})")
    elif eds >= 0.5:
        confidence_factors.append(f"ℹ️ Standard email domain ({eds:.2f})")
    else:
        confidence_factors.append(f"ℹ️ Basic email domain ({eds:.2f}) — weak confidence signal, not penalised")

    if confidence_score >= 0.7:
        confidence_factors.append(f"🔒 Confidence Score: {confidence_score:.2f} — HIGH data quality")
    elif confidence_score >= 0.4:
        confidence_factors.append(f"🔒 Confidence Score: {confidence_score:.2f} — MODERATE data quality")
    else:
        confidence_factors.append(f"🔒 Confidence Score: {confidence_score:.2f} — LOW data quality")
        
    if confidence_score < 0.3:
        warning_msg = "⚠️ Low confidence due to limited data signals — consider manual review"
        confidence_factors.append(warning_msg)
        if len(top_reasons) < 3: top_reasons.append(warning_msg)

    # ═════════════════════════════════════════════════════════════════════
    # FINAL REASONING & SUMMARY
    # ═════════════════════════════════════════════════════════════════════
    final_reasoning = f"Formula: {value_score:.2f} × (0.70 + 0.30 × {confidence_score:.2f}) = {signal_score:.2f}. "
    
    val_str = "strong business value" if value_score >= 0.7 else "moderate business value" if value_score >= 0.4 else "low business value"
    conf_str = "high confidence" if confidence_score >= 0.7 else "moderate confidence" if confidence_score >= 0.4 else "lower confidence/missing data"

    if value_score >= 0.7 and confidence_score < 0.4:
        final_reasoning += "💡 High value overrides low confidence — lead is worth pursuing despite data gaps."
    elif value_score < 0.4 and confidence_score >= 0.7:
        final_reasoning += "💡 Good data quality but low business value — consider for nurturing."
    elif value_score >= 0.7 and confidence_score >= 0.7:
        final_reasoning += "🌟 Both value and confidence are strong — top-tier lead."
    else:
        final_reasoning += "Average overall profile."

    # Human-readable summary
    summary = f"Lead has {val_str}"
    
    # Pick a quick specific reason for value
    if signals.get("is_decision_maker", 0) >= 1.0:
        summary += " due to their decision-maker role"
    elif eng >= 0.7:
        summary += " driven by high engagement"
    elif ml_reply >= 0.8:
        summary += " based on strong ML predictions"
    
    summary += f", and offers {conf_str}"
    
    if signals.get("is_business_email", 0) < 1.0:
        summary += " due to personal/free email usage."
    elif confidence_score >= 0.7:
        summary += " with a verified professional profile."
    else:
        summary += "."

    # Ensure we always have top_reasons (grab from value_factors if needed)
    for r in value_factors:
        if len(top_reasons) >= 3:
            break
        if "✅" in r and r not in top_reasons:
            top_reasons.append(r)

    # Legacy flat reasons array for backwards compat
    all_reasons = []
    all_reasons.append("── VALUE SIGNALS ──")
    all_reasons.extend(value_factors)
    all_reasons.append("── CONFIDENCE SIGNALS ──")
    all_reasons.extend(confidence_factors)
    all_reasons.append("── FINAL ──")
    all_reasons.append(final_reasoning)

    return {
        "value_factors": value_factors,
        "confidence_factors": confidence_factors,
        "final_reasoning": final_reasoning,
        "summary": summary,
        "top_reasons": top_reasons[:3],
        "reasons": all_reasons
    }
