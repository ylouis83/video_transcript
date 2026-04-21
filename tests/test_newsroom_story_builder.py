from newsroom_story_builder import build_newsroom_story


def test_build_newsroom_story_limits_to_three_axes():
    metadata = {"title": "SpaceX IPO clip"}
    transcript = (
        "SpaceX may go public at a very high valuation. "
        "Revenue is around 15 billion dollars. "
        "The better entry may be 12 to 18 months after listing."
    )
    result = build_newsroom_story(metadata, transcript)

    assert result["story_mode"] == "newsroom"
    assert result["title"] == "SpaceX IPO clip"
    assert [frame["headline"] for frame in result["frames"]] == [
        "未必便宜",
        "估值太满",
        "收入偏紧",
        "更像融资",
        "先看兑现",
        "再看一年",
    ]
    assert result["frames"][0]["pip_mode"] == "lead"
    assert all(frame["source"] == "来源：原 Shorts 视频整理" for frame in result["frames"])
    assert "首发定价通常会先反映想象力" in result["frames"][0]["angle_body"]
    assert "估值越满" in result["frames"][1]["angle_body"]
    assert "并表可以放大想象空间" in result["frames"][2]["angle_body"]
    assert "融资效率和二级市场回报" in result["frames"][3]["angle_body"]
    assert "市场后面还是会追着经营节奏要答案" in result["frames"][4]["angle_body"]
    assert "一年后看到的才更接近真实经营" in result["frames"][5]["angle_body"]


def test_build_newsroom_story_removes_scare_quotes_and_bridge_phrases():
    metadata = {"title": "SpaceX IPO clip"}
    transcript = "“换句话说”，对市场来说，SpaceX is pricing in perfection."
    result = build_newsroom_story(metadata, transcript)

    all_text = "\n".join(
        [frame["headline"] + "\n" + frame["body"] for frame in result["frames"]]
    )
    assert "“" not in all_text
    assert "”" not in all_text
    assert "换句话说" not in all_text
    assert "对市场来说" not in all_text


def test_build_newsroom_story_changes_for_non_spacex_transcript():
    metadata = {"title": "Another clip"}
    transcript = (
        "OpenAI is hiring more engineers. "
        "The company is preparing more inference capacity. "
        "Customers are watching deployment costs closely."
    )
    result = build_newsroom_story(metadata, transcript)

    assert set(result.keys()) == {"story_mode", "title", "frames"}
    assert result["story_mode"] == "newsroom"
    assert result["title"] == "Another clip"
    assert all(
        set(frame.keys()) == {"headline", "body", "angle_title", "angle_body", "angle_note", "source", "pip_mode", "angle_fact", "angle_watch"}
        for frame in result["frames"]
    )
    assert len(result["frames"]) == 6
    assert result["frames"][0]["headline"] == "消息先到"
    assert "Another clip" in result["frames"][0]["body"]
    assert "OpenAI is hiring more engineers" in result["frames"][0]["body"]
    assert "The company is preparing more inference capacity" in result["frames"][1]["body"]
    assert result["frames"][0]["angle_title"] == "先看原话"


def test_build_newsroom_story_does_not_false_positive_on_finance_language():
    metadata = {"title": "Capital markets clip"}
    transcript = (
        "The company may go public after listing preparations. "
        "Analysts are debating a 15 billion dollar valuation. "
        "Investors still want clearer revenue disclosures."
    )
    result = build_newsroom_story(metadata, transcript)

    assert result["frames"][0]["headline"] == "消息先到"
    assert result["frames"][0]["body"].startswith("Capital markets clip\nThe company may go public after listing preparations")


def test_build_newsroom_story_uses_safe_default_for_empty_transcript():
    metadata = {}
    transcript = "   "
    result = build_newsroom_story(metadata, transcript)

    assert result["frames"][0]["headline"] == "消息先到"
    assert result["frames"][0]["body"].startswith("原始转录为空，先保留标题信息")


def test_build_newsroom_story_supports_barchart_spacex_longform_mode():
    metadata = {"title": "SpaceX IPO Explained: Why Smart Money Is Staying Away"}
    transcript = (
        "61% say no to buying SpaceX on IPO day. "
        "The valuation is around 1.5 trillion dollars with only 5% of the company coming to market. "
        "After 15 days the stock may be added to the Nasdaq and passive buyers could be forced in. "
        "The speakers compare this to an initial bump that later fades and say IPOs are often exit liquidity vehicles. "
        "They mention Circle as a recent example. "
        "There are also rumors about a Tesla and SpaceX merger. "
        "They discuss related space stocks like BKSY and ASTS."
    )

    result = build_newsroom_story(metadata, transcript, chapter_count=10)

    assert result["story_mode"] == "newsroom-longform"
    assert result["title"] == "SpaceX IPO 为什么未必是买点"
    assert len(result["frames"]) == 10
    assert [frame["headline"] for frame in result["frames"]] == [
        "先给结论",
        "估值太高",
        "流通太少",
        "15天规则",
        "被动买盘",
        "退出流动性",
        "首日别追",
        "马斯克叙事",
        "替代标的",
        "一年再看",
    ]
    all_text = "\n".join(
        [frame["headline"] + "\n" + frame["body"] + "\n" + frame["angle_body"] for frame in result["frames"]]
    )
    assert "1.5 万亿美元" in all_text
    assert "5%" in all_text
    assert "15天" in all_text
    assert "退出流动性" in all_text
    assert "BKSY" in all_text
    assert "ASTS" in all_text
    assert "热度退下来之后" in "\n".join(frame["angle_watch"] for frame in result["frames"])
