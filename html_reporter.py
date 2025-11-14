# html_reporter.py
#
# PRO HTML report generator for Facebook Scraper Pro
# Includes:
# - Dark UI
# - Grouping by author (expand/collapse)
# - Filters
# - Sorting
# - Rich post rendering (images, links)
# - URL + date in title

from html import escape as esc
import datetime


def generate_html_report(posts, page_url, generated_label, out_path):

    # --- Convert date into dd/mm/yy - HH:MM:SS ---
    try:
        dt = datetime.datetime.strptime(generated_label, "%Y %B, %d - %H:%M:%S")
        formatted_date = dt.strftime("%d/%m/%y - %H:%M:%S")
    except:
        formatted_date = generated_label

    # --- Group posts by author ---
    groups = {}
    for p in posts:
        a = p.get("author") or "Unknown Author"
        groups.setdefault(a, []).append(p)

    sorted_authors = sorted(groups.keys(), key=lambda x: x.lower())

    # --- Start HTML ---
    h = []
    h.append("<!DOCTYPE html>")
    h.append("<html><head><meta charset='utf-8'><title>Facebook Scraper Pro</title>")

    # --- CSS ---
    h.append("""
<style>
body {
    background:#0d1117;
    color:#e6edf3;
    font-family:Segoe UI,Roboto,Arial,sans-serif;
    padding:25px;
}
h1 {
    color:#58a6ff;
    margin-bottom:2px;
}
.subtitle-small {
    font-size:14px;
    opacity:0.8;
    margin-bottom:15px;
}
a { color:#58a6ff; }
.controls {
    display:flex;
    gap:15px;
    flex-wrap:wrap;
    margin-top:20px;
    margin-bottom:25px;
}
input[type="text"], select {
    padding:6px 10px;
    background:#161b22;
    border:1px solid #30363d;
    color:#e6edf3;
    border-radius:6px;
}
.author-group {
    margin-top:25px;
    border:1px solid #30363d;
    border-radius:8px;
    background:#161b22;
}
.author-header {
    padding:12px;
    font-size:18px;
    cursor:pointer;
    background:#1d242d;
}
.author-header:hover {
    background:#212c36;
}
.author-body {
    display:none;
    padding:10px 12px;
}
.post-card {
    margin:12px 0;
    background:#0f141a;
    border:1px solid #30363d;
    border-radius:8px;
    padding:12px;
}
.post-header {
    display:flex;
    justify-content:space-between;
    font-size:14px;
}
.post-meta {
    font-size:12px;
    color:#8b949e;
    margin-top:4px;
}
.post-text {
    margin-top:8px;
    white-space:pre-wrap;
}
.thumb-img {
    max-width:180px;
    border-radius:6px;
    border:1px solid #30363d;
    margin:4px;
}
.links, .images {
    margin-top:10px;
    font-size:12px;
}
.total-posts {
    font-size:14px;
    opacity:0.9;
    margin-left:10px;
    color:#58a6ff;
    align-self:center;
}
.page-url {
    font-size:15px;
    color:#58a6ff;
    opacity:0.9;
    margin-bottom:20px;
    font-weight:500;
}      
</style>
""")

    # --- JavaScript ---
    h.append("""
<script>

function toggleGroup(id){
    const el = document.getElementById(id);
    el.style.display = (el.style.display === "none" || !el.style.display) ? "block" : "none";
}

function applyFilters(){
    const textQ = document.getElementById("flt_text").value.toLowerCase();
    const authorQ = document.getElementById("flt_author").value;

    document.querySelectorAll(".author-group").forEach(group=>{
        const author = group.getAttribute("data-author");
        let groupVisible = true;

        if(authorQ !== "ALL" && author !== authorQ){
            groupVisible = false;
        }

        let anyVisible = false;

        group.querySelectorAll(".post-card").forEach(card=>{
            const blob = card.getAttribute("data-search");
            let visible = true;

            if(textQ && !blob.includes(textQ)) visible = false;

            card.style.display = visible ? "" : "none";
            if(visible) anyVisible = true;
        });

        group.style.display = (groupVisible && anyVisible) ? "" : "none";
    });
}


function applySorting() {
    const mode = document.getElementById("sort_mode").value;
    const container = document.getElementById("groups_container");
    const groups = Array.from(container.children);

    groups.sort((a,b)=>{
        const a_name = a.getAttribute("data-author").toLowerCase();
        const b_name = b.getAttribute("data-author").toLowerCase();
        const a_count = parseInt(a.getAttribute("data-count"));
        const b_count = parseInt(b.getAttribute("data-count"));

        switch(mode){
            case "az":
                return a_name.localeCompare(b_name);
            case "za":
                return b_name.localeCompare(a_name);
            case "count_desc":
                return b_count - a_count;
            case "count_asc":
                return a_count - b_count;
        }
    });

    groups.forEach(g=>container.appendChild(g));
}


document.addEventListener("DOMContentLoaded", () => {
    let total = document.querySelectorAll(".post-card").length;
    document.getElementById("total_posts_inline").textContent = total;
});

</script>
""")

    # Title
    h.append("<h1 style='margin-bottom:6px;'>Facebook Scraper Pro</h1>")

    # URL + Total posts (on same line)
    h.append(
        f"<div class='page-url'>{esc(page_url)}"
        f" - Total Posts: <span id='total_posts_inline'></span></div>"
)

    # --- Filters + Sorting + Total posts ---
    h.append("""
<div class='controls'>
    <input id='flt_text' type='text' placeholder='Search text...' onkeyup='applyFilters()'>

    <select id='flt_author' onchange='applyFilters()'>
        <option value='ALL'>Authors</option>
""")

    for a in sorted_authors:
        h.append(f"<option value='{esc(a)}'>{esc(a)}</option>")

    h.append("""
    </select>

    <select id="sort_mode" onchange="applySorting()">
        <option value="az">Sort</option>
        <option value="az">Author (Asc.)</option>
        <option value="za">Author (Des.)</option>
        <option value="count_desc">Posts (High First)</option>
        <option value="count_asc">Posts (Low First)</option>
    </select>

    <span id="total_posts" class="total-posts"></span>

</div>
""")

    # --- Author groups ---
    h.append("<div id='groups_container'>")

    gid = 0
    for author in sorted_authors:
        posts_list = groups[author]
        gid += 1
        group_id = f"group_{gid}"

        h.append(
            f"<div class='author-group' data-author='{esc(author)}' data-count='{len(posts_list)}'>"
            f"<div class='author-header' onclick=\"toggleGroup('{group_id}')\">"
            f"{esc(author)} ({len(posts_list)} posts)"
            f"</div>"
            f"<div class='author-body' id='{group_id}'>"
        )

        for p in posts_list:
            idx = p.get("post_index")
            text = p.get("text") or ""
            timestamp = p.get("timestamp") or ""
            permalink = p.get("permalink") or ""
            images = p.get("images") or []
            links = p.get("links") or []

            search_blob = f"{text} {author} {timestamp} {permalink}".lower()

            h.append(f"<div class='post-card' data-search='{esc(search_blob)}'>")

            h.append(
                f"<div class='post-header'>"
                f"<div><strong>Post {idx}</strong></div>"
                f"<div class='post-meta'>{esc(timestamp)}</div>"
                f"</div>"
            )

            if permalink:
                h.append(
                    f"<div class='post-meta'>Permalink: "
                    f"<a href='{esc(permalink)}' target='_blank'>{esc(permalink)}</a>"
                    f"</div>"
                )

            if text:
                h.append(f"<div class='post-text'>{esc(text)}</div>")

            if images:
                h.append("<div class='images'><strong>Images:</strong><br>")
                for src in images[:8]:
                    h.append(
                        f"<a href='{esc(src)}' target='_blank'>"
                        f"<img class='thumb-img' src='{esc(src)}'>"
                        f"</a>"
                    )
                h.append("</div>")

            if links:
                h.append("<div class='links'><strong>Links:</strong>")
                for lk in links[:8]:
                    h.append(
                        f"<div>- <a href='{esc(lk['href'])}' target='_blank'>{esc(lk['text'])}</a></div>"
                    )
                h.append("</div>")

            h.append("</div>")  # post-card

        h.append("</div></div>")  # group

    h.append("</div>")  # groups_container

    # Close doc
    h.append("</body></html>")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(h))
