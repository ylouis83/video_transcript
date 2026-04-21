from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
import re


@dataclass(frozen=True)
class NewsroomFrame:
    headline: str
    body: str
    angle_title: str
    angle_body: str
    angle_note: str
    source: str
    pip_mode: str
    angle_fact: str = ""
    angle_watch: str = ""


_QUOTE_REPLACEMENTS = {
    "“": "",
    "”": "",
    "换句话说": "",
    "对市场来说": "",
}

_SPACEX_BRAND_PATTERN = r"\bSpaceX\b"
_SPACEX_LISTING_PATTERNS = [
    r"\bIPO\b",
    r"\bgo public\b",
    r"\blisting\b",
]
_SPACEX_SUPPORT_PATTERNS = [
    r"\bvaluation\b",
    r"\b15\s*billion\b",
    r"\b12\s*to\s*18\s*months\b",
]
_SPACEX_BARCHART_LONGFORM_PATTERNS = [
    r"\b61%\b",
    r"\b1\.5\s*trillion\b",
    r"\b5%\b",
    r"\b15\s*days?\b",
    r"\bexit liquidity\b",
    r"\bBKSY\b",
    r"\bASTS\b",
]


def _clean_text(text: str) -> str:
    cleaned = text
    for needle, replacement in _QUOTE_REPLACEMENTS.items():
        cleaned = cleaned.replace(needle, replacement)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _derive_title(metadata: dict[str, Any]) -> str:
    raw_title = metadata.get("title", "")
    if raw_title is None:
        return "科技简报"

    title = str(raw_title).strip()
    if not title or title == "None":
        return "科技简报"
    return title


def _looks_like_spacex_ipo_clip(title: str, transcript_text: str) -> bool:
    haystack = f"{title} {transcript_text}"
    has_brand = bool(re.search(_SPACEX_BRAND_PATTERN, haystack, re.IGNORECASE))
    has_listing = any(re.search(pattern, haystack, re.IGNORECASE) for pattern in _SPACEX_LISTING_PATTERNS)
    has_support = any(re.search(pattern, haystack, re.IGNORECASE) for pattern in _SPACEX_SUPPORT_PATTERNS)
    return has_brand and has_listing and has_support


def _looks_like_spacex_barchart_explainer(title: str, transcript_text: str) -> bool:
    haystack = f"{title} {transcript_text}"
    if "smart money is staying away" not in haystack.lower():
        return False
    if not re.search(_SPACEX_BRAND_PATTERN, haystack, re.IGNORECASE):
        return False
    return sum(
        1 for pattern in _SPACEX_BARCHART_LONGFORM_PATTERNS if re.search(pattern, haystack, re.IGNORECASE)
    ) >= 5


def _split_sentences(text: str) -> list[str]:
    pieces = re.split(r"(?<=[.!?。！？])\s+", text)
    return [piece.strip(" 。！？!?") for piece in pieces if piece.strip(" 。！？!?")]


def _build_generic_frames(title: str, transcript_text: str) -> list[NewsroomFrame]:
    sentences = _split_sentences(transcript_text)
    if not sentences:
        sentences = [transcript_text.strip() or "原始转录为空，先保留标题信息"]

    focus = title if title != "科技简报" else sentences[0]
    body_source = sentences[:5]
    while len(body_source) < 5:
        body_source.append(body_source[-1])

    return [
        NewsroomFrame(
            headline="消息先到",
            body=f"{focus}\n{body_source[0]}",
            angle_title="先看原话",
            angle_body="这条内容先把变化抛出来，但第一句通常只负责制造注意力。真正值得看的，是后面有没有补条件、补口径，或者直接改写前一句的力度。",
            angle_note="先分清事实和判断，再决定值不值得放大。",
            source="来源：原 Shorts 视频整理",
            pip_mode="lead",
            angle_watch="先看原话，再看条件，最后再看市场怎么接这条信息。",
        ),
        NewsroomFrame(
            headline="先看变化",
            body=f"{body_source[0]}\n{body_source[1]}",
            angle_title="变化在哪里",
            angle_body="如果第二句开始补条件、补时间点，说明这条信息已经不只是简单播报，而是在往更复杂的解释走。这个时候，比结论更重要的是条件。",
            angle_note="同一条短视频里，补充条件往往比结论更重要。",
            source="来源：原 Shorts 视频整理",
            pip_mode="support",
            angle_watch="如果第二句就开始补条件，说明这条内容本身就没有那么简单。",
        ),
        NewsroomFrame(
            headline="影响扩大",
            body=f"{body_source[1]}\n{body_source[2]}",
            angle_title="往谁身上落",
            angle_body="这一层不只是信息本身，而是它会先影响谁、会改变哪些预期，市场通常先交易这个部分。",
            angle_note="对象变了，含义就会跟着变。",
            source="来源：原 Shorts 视频整理",
            pip_mode="support",
            angle_watch="先看影响落到谁，再看资金会不会先交易这个变化。",
        ),
        NewsroomFrame(
            headline="还要验证",
            body=f"{body_source[2]}\n{body_source[3]}",
            angle_title="先别写死",
            angle_body="短视频里的判断往往给得更快，但能不能成立，还得看后续有没有更完整的口径和兑现信息。",
            angle_note="没有后续验证，再强的判断也只能先记一层。",
            source="来源：原 Shorts 视频整理",
            pip_mode="support",
            angle_watch="越早下重结论，越容易被后续信息打回去。",
        ),
        NewsroomFrame(
            headline="别急下结论",
            body=f"{body_source[3]}\n{body_source[4]}",
            angle_title="结论往后放",
            angle_body="如果前面的事实还在变化，结论就不该一次收死，真正重要的是后面哪一件事会改写它。",
            angle_note="把结论往后放，通常比提前升维更稳。",
            source="来源：原 Shorts 视频整理",
            pip_mode="support",
            angle_watch="真正能改写判断的，往往是后面一两步兑现而不是当下情绪。",
        ),
        NewsroomFrame(
            headline="继续看后面",
            body="更值得观察的\n是这条信息接下来怎么兑现",
            angle_title="最后看兑现",
            angle_body="短视频能给你方向，但真正决定值不值得继续追踪的，通常是后面一两步有没有按这个方向发生。",
            angle_note="观察点出现以后，再决定要不要重写判断。",
            source="来源：原 Shorts 视频整理",
            pip_mode="support",
            angle_watch="把观察点留下来，后面才能知道这条内容值不值得继续追。",
        ),
    ]


def _build_generic_longform_frames(title: str, transcript_text: str, chapter_count: int) -> list[NewsroomFrame]:
    sentences = _split_sentences(transcript_text)
    if not sentences:
        sentences = [transcript_text.strip() or "原始转录为空，先保留标题信息"]

    headlines = [
        "先给结论",
        "先看变化",
        "再看数字",
        "条件在哪",
        "影响对象",
        "争议出现",
        "判断拉开",
        "风险落点",
        "后续验证",
        "最后看什么",
    ]
    angle_titles = [
        "先把新闻讲清",
        "变化先落一层",
        "数字先不混写",
        "条件决定力度",
        "对象不同含义不同",
        "争议决定交易方向",
        "市场会先交易分歧",
        "风险先落到兑现",
        "验证比结论更值钱",
        "最后收在事件上",
    ]
    angle_notes = [
        "先把事实、对象和时间点放稳，再谈结论。",
        "第二层通常决定这条信息能不能继续发酵。",
        "同一份材料里的数字，先分清口径再比较。",
        "少一个条件，判断强度就会变。",
        "对象一换，市场给出的价格也会跟着换。",
        "争议越大，越容易变成交易理由。",
        "分歧不是噪音，往往就是机会和风险的来源。",
        "如果兑现慢一步，估值就会先退一步。",
        "没有验证，再顺的叙述也只能先记一层。",
        "把重写判断的触发器留给后面的事件。",
    ]

    frames: list[NewsroomFrame] = []
    total = min(chapter_count, len(headlines))
    chunk_size = max(1, len(sentences) // total)

    for index in range(total):
        start = index * chunk_size
        end = len(sentences) if index == total - 1 else min(len(sentences), start + chunk_size)
        chunk = sentences[start:end] or [sentences[-1]]
        body_lines = chunk[:2]
        angle_lines = chunk[1:4] or chunk[:2]
        frames.append(
            NewsroomFrame(
                headline=headlines[index],
                body="\n".join(body_lines[:2]),
                angle_title=angle_titles[index],
                angle_body=" ".join(angle_lines[:3]),
                angle_note=angle_notes[index],
                source=f"来源：{title} 视频整理",
                pip_mode="lead" if index == 0 else "support",
                angle_watch="这一章先记方向，真正的验证留给后面的数据、口径和市场反应。",
            )
        )

    return frames


def _build_spacex_barchart_longform_frames() -> list[NewsroomFrame]:
    return [
        NewsroomFrame(
            headline="先给结论",
            body="SpaceX 一旦上市，会是今年最受关注的 IPO 之一。\n但这期节目一开头给出的判断就很明确：聪明钱不急着在第一天冲进去。",
            angle_title="投票先把态度摆出来",
            angle_body="原视频开场先做了一个 X 上投票，61% 的参与者表示不会在 IPO 当天买入。这个开头不是噱头，而是先把整期讨论定成谨慎，而不是追热度。",
            angle_note="好公司和好买点不是一回事，节目先把这两件事拆开了。",
            source="来源：Barchart 视频整理",
            pip_mode="lead",
            angle_watch="如果开场先把态度定成谨慎，后面的每一段都要按这个框架往下看。",
        ),
        NewsroomFrame(
            headline="估值太高",
            body="节目把焦点很快拉到 1.5 万亿美元估值。\n如果按这个区间上市，市场一开始面对的就是一个被高预期包住的资产。",
            angle_title="贵不只是贵在数字",
            angle_body="问题不只是估值本身有多高，而是这个估值已经把增长、叙事和融资环境一起提前反映了。定价越满，后面留给公开市场的回报空间就越窄。",
            angle_note="高估值先吃掉容错，后面每一份财报都要证明自己没有失手。",
            source="来源：Barchart 视频整理",
            pip_mode="support",
            angle_watch="估值越早打满，后面越像在持续交作业，而不是慢慢建立预期。",
        ),
        NewsroomFrame(
            headline="流通太少",
            body="原视频接着往下拆的，是只有 5% 股份进入流通。\n按 1.5 万亿美元估值和 750 亿美元募资额来算，真正能交易的 float 并不多。",
            angle_title="浮动盘小，价格更容易被挤上去",
            angle_body="当流通盘太小，市场看到的不是充裕供给，而是一个容易被情绪和资金推动的标的。对散户来说，这意味着首日价格更容易偏离基本面。",
            angle_note="float 不够大，IPO 更容易先变成稀缺品交易。",
            source="来源：Barchart 视频整理",
            pip_mode="support",
            angle_watch="真正能交易的筹码越少，价格就越容易被资金面先推着走。",
        ),
        NewsroomFrame(
            headline="15天规则",
            body="节目最特别的一段，是把 15 天后的纳指纳入规则单独拎出来。\n如果届时被纳入相关指数，后面会出现一批机制性买盘。",
            angle_title="规则本身会改价格路径",
            angle_body="这条规则改变的不是公司价值，而是股票上市后前几周的交易结构。还没等到第一份完整财报，指数和被动资金就可能先把价格往上顶。",
            angle_note="规则先改的是供需，不是基本面。",
            source="来源：Barchart 视频整理",
            pip_mode="support",
            angle_watch="短期价格先被规则推着走，并不代表公司价值同步改了。",
        ),
        NewsroomFrame(
            headline="被动买盘",
            body="原视频顺着这条规则往下推，认为上市初期最容易出现的是被动买盘推高。\n一旦所有人都知道后面有人要买，最先进去的人也会提前抢跑。",
            angle_title="首日上涨不一定说明值这个价",
            angle_body="节目用交易员视角讲得很直白：当市场都在等下一波被动买盘时，价格先涨反而更像预支后面的买力。这样的上涨更像结构性挤压，而不是价值重估。",
            angle_note="价格先涨，未必说明公司突然更值钱，只可能说明后面的买盘被提前交易了。",
            source="来源：Barchart 视频整理",
            pip_mode="support",
            angle_watch="当市场都知道下一波资金会来，最先发生的往往是抢跑。",
        ),
        NewsroomFrame(
            headline="退出流动性",
            body="到了中段，节目把 IPO 的本质讲得更直接：很多 IPO 先是退出流动性工具。\n最先获得流动性的，通常不是二级市场后来者，而是更早持股的人。",
            angle_title="IPO 先服务谁",
            angle_body="节目拿 Circle 举例，就是为了说明一个常见现象：公司上市以后，最早的任务往往不是给公开市场留便宜，而是给早期股东和原有资本结构打开退出通道。",
            angle_note="如果一笔 IPO 的首要功能是退出流动性，首发阶段就更难天然便宜。",
            source="来源：Barchart 视频整理",
            pip_mode="support",
            angle_watch="谁最先拿到流动性，决定了这笔交易首先服务的是谁。",
        ),
        NewsroomFrame(
            headline="首日别追",
            body="节目没有否认长期价值，但它把买点明显往后推。\n更合理的观察窗口，不是上市当天，而是 3 个月、6 个月，甚至 1 年之后。",
            angle_title="先让市场自己找锚",
            angle_body="上市初期先交易的是情绪、流通盘和规则红利，后面才会慢慢回到收入、利润和现金流。等市场先自己把锚定价找出来，再决定要不要进，风险会小很多。",
            angle_note="先让热度过去，再看经营接不接得住，是这期视频反复强调的逻辑。",
            source="来源：Barchart 视频整理",
            pip_mode="support",
            angle_watch="等流通盘、情绪和规则红利先消化一轮，再看价格更接近真实锚点。",
        ),
        NewsroomFrame(
            headline="马斯克叙事",
            body="后半段又把市场最容易兴奋的部分带了出来：Tesla 和 SpaceX 的合并传闻。\n这类叙事一旦升温，会继续把情绪和估值往上推。",
            angle_title="故事会抬温度，不会自动抬价值",
            angle_body="节目提这层，不是在证明并购一定发生，而是在提醒一件事：只要马斯克叙事还在扩散，IPO 定价就不只是一家公司上市，而会被卷进更大的想象空间。",
            angle_note="叙事越大，市场越容易先给溢价，后面也越容易回头要兑现。",
            source="来源：Barchart 视频整理",
            pip_mode="support",
            angle_watch="故事能把价格抬起来，但留不留得住，还得回到兑现。",
        ),
        NewsroomFrame(
            headline="替代标的",
            body="节目最后还把 BKSY、ASTS 这些相关太空标的一起带了进来。\nSpaceX 的热度一旦起来，相关概念股通常也会被情绪顺带拉高。",
            angle_title="热点不会只停在主角身上",
            angle_body="这段的意思不是说这些股票和 SpaceX 等价，而是市场在追主题时，经常会先把同赛道的标的一起抬起来。谁能真正留下来，最后还得回到各自业务质量。",
            angle_note="主题先扩散，分化通常后到。被带热的股票，后面更需要单独验证。",
            source="来源：Barchart 视频整理",
            pip_mode="support",
            angle_watch="主题交易先扩散，再分化，最后还是各自回到自己的业绩上。",
        ),
        NewsroomFrame(
            headline="一年再看",
            body="这期视频最后真正想留下的，不是首日判断，而是时间点。\n更值得看的，是上市后 12 到 18 个月，估值会不会回到能被基本面接住的位置。",
            angle_title="真正的答案在后面",
            angle_body="到了那个时间点，市场已经看过财报、看过流通盘、也看过热度退潮后的交易结构。那时候再回头看，才更接近这笔 IPO 留给公开市场的是热闹，还是回报。",
            angle_note="真正会改写判断的，是上市后一年里的兑现节奏，而不是上市当天的掌声。",
            source="来源：Barchart 视频整理",
            pip_mode="support",
            angle_watch="真正的观察点，是热度退下来之后，估值还能不能被业绩接住。",
        ),
    ]


def build_newsroom_story(metadata: dict[str, Any], transcript_text: str, chapter_count: int = 6) -> dict[str, Any]:
    title = _derive_title(metadata)
    cleaned_transcript = _clean_text(transcript_text)

    if chapter_count >= 10 and _looks_like_spacex_barchart_explainer(title, cleaned_transcript):
        frames = _build_spacex_barchart_longform_frames()
        return {
            "story_mode": "newsroom-longform",
            "title": "SpaceX IPO 为什么未必是买点",
            "frames": [asdict(frame) for frame in frames],
        }

    if _looks_like_spacex_ipo_clip(title, cleaned_transcript):
        frames = [
            NewsroomFrame(
                headline="未必便宜",
                body="明星资产先拉满想象力。\n公开市场未必立刻便宜。",
                angle_title="不是稀缺就会便宜",
                angle_body="明星资产一旦带着稀缺叙事上市，首发定价通常会先反映想象力，而不是先留安全边际。对公开市场来说，越是自带明星光环，越不容易在第一天捡到便宜。",
                angle_note="稀缺性会先抬情绪，不会先给折价。真正便宜的时候，往往出现在热度开始退潮之后。",
                source="来源：原 Shorts 视频整理",
                pip_mode="lead",
                angle_watch="稀缺叙事先抬预期，不会先送出低价筹码。",
            ),
            NewsroomFrame(
                headline="估值太满",
                body="估值区间已经很高。\n增长和融资前提被一次打满。",
                angle_title="高估值先吃掉回报",
                angle_body="如果市场一开始就按最乐观情形定价，后面的财报就不是证明公司优秀，而是在证明它没有失手。估值越满，公开市场能分到的回报空间就越窄。",
                angle_note="定价越高，容错越低。只要增长和利润有一项没跟上，估值就会先往下修。",
                source="来源：原 Shorts 视频整理",
                pip_mode="support",
                angle_watch="市场把前提先打满，后面每一步兑现都会被放大检查。",
            ),
            NewsroomFrame(
                headline="收入偏紧",
                body="当前收入还难接住高定价。\n并表以后安全边际也不厚。",
                angle_title="收入还接不住",
                angle_body="眼下的问题不是故事不够大，而是现阶段收入和利润厚度，还不足以轻松承接这么高的定价。把相关资产并表可以放大想象空间，但未必同步抬高安全边际。",
                angle_note="并表能放大想象空间，未必同步放大安全边际。最后还是要看收入质量和现金流能不能接住。",
                source="来源：原 Shorts 视频整理",
                pip_mode="support",
                angle_watch="收入接不住估值，价格就会先替基本面回头重定价。",
            ),
            NewsroomFrame(
                headline="更像融资",
                body="这更像高位融资窗口。\n首发太满，回报会被提前透支。",
                angle_title="先满足融资窗口",
                angle_body="这种时点更像公司趁情绪最热时把融资条件做到最好，而不是给公开市场留一个舒服的买入位置。融资效率和二级市场回报，很多时候不是同一件事。",
                angle_note="融资效率和投资回报，不一定站在同一边。对公司是好窗口，对二级市场不一定是好价格。",
                source="来源：原 Shorts 视频整理",
                pip_mode="support",
                angle_watch="对公司是融资窗口，对公开市场未必是舒服买点。",
            ),
            NewsroomFrame(
                headline="先看兑现",
                body="后面真正要看增长兑现。\n最后都要落到现金流上。",
                angle_title="最终回到兑现",
                angle_body="火箭、星链和相关业务最后都要落到收入增速、利润率和现金流。热度可以先抬估值，但抬不出长期兑现，市场后面还是会追着经营节奏要答案。",
                angle_note="故事越大，市场越会追着兑现节奏要答案。真正压不住的不是争议，而是连续几个季度的数据跟不上。",
                source="来源：原 Shorts 视频整理",
                pip_mode="support",
                angle_watch="热度抬得快，兑现慢一步，回撤就会先出现。",
            ),
            NewsroomFrame(
                headline="再看一年",
                body="别急着看上市当天。\n一年后估值会不会回落。",
                angle_title="一年后才见真章",
                angle_body="上市当天看到的是情绪和定价，一年后看到的才更接近真实经营能不能把估值留住。那时候再回头看今天的高估值，才知道哪些预期被兑现了，哪些只是热闹。",
                angle_note="真正的分水岭，是回调后还能不能被基本面接住。时间一拉长，情绪溢价通常会先被挤掉。",
                source="来源：原 Shorts 视频整理",
                pip_mode="support",
                angle_watch="真正值得看的不是首日涨跌，而是热度退潮后的承接力。",
            ),
        ]
    elif chapter_count >= 10:
        frames = _build_generic_longform_frames(title, cleaned_transcript, chapter_count)
        return {
            "story_mode": "newsroom-longform",
            "title": title,
            "frames": [asdict(frame) for frame in frames],
        }
    else:
        frames = _build_generic_frames(title, cleaned_transcript)

    return {
        "story_mode": "newsroom",
        "title": title,
        "frames": [asdict(frame) for frame in frames],
    }
