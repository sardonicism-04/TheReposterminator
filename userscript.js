// ==UserScript==
// @name           Repost comment viewer
// @description    Quickly view TheReposterminator's comments
// @author         sardonicism-04
// @run-at         document-idle
// @include        https://www.reddit.com/*
// @include        https://old.reddit.com/*
// ==/UserScript==

const REuslash = /\/u\/.*/;
const REpost = /https\:\/\/redd\.it\/.*/;
const REreport = /TheReposterminator\: Possible repost \( \d*? matches \| \d*? removed\/deleted \)/;
const popupCreator = `
const openWindow = (content) => {
    let popup = window.open("", null, "height=600,width=1000,status=yes,toolbar=no,menubar=no,location=no");
    const addStyle = (styleString) => {
        const style = popup.document.createElement('style');
        style.textContent = styleString;
        popup.document.head.append(style);
    }
    addStyle(\`
        table, th, td {
          border: 1px solid black;
          border-collapse: collapse;
        }
        * {
            font-family: 'sans-serif';
        }\`
    );
    popup.document.body.innerHTML = content;
    for (let link of popup.document.links) {
        link = link.href;
        if (!link.match(${REuslash}) && !link.match(${REpost})) {
            let img = popup.document.createElement('img');
            img.src = link;
            img.height = '100';
            popup.document.body.appendChild(img);
        }
    }
}
`;

const generateSelector = (object) => {
    let _id = `#${object.id}`;
    let classes = new Array();
    object.classList.forEach(item => classes.push(`.${item}`));
    classes = classes.join('')
    return `${_id}${classes}`
}

const getData = async (urlString, selector) => {
    let url = new URL(urlString);
    url.search = '';
    let resp = await fetch(
        url.toString(),
        {method: 'GET'});
    let data = await resp.json();
    for (let comment_raw of data[1].data.children) {
        let comment = comment_raw.data
        if (comment.author === 'TheReposterminator') {
            return comment.body_html.replace(/&lt;/g, '<').replace(/&gt;/g, '>');
        }
    }
}

const addStyle = (styleString) => {
    const style = document.createElement('style');
    style.textContent = styleString;
    document.head.append(style);
}

const updatePosts = () => {
    if ( document.readyState !== 'complete' ) return;
    let links = document.querySelectorAll('.linklisting .link,div.Post');
    for (let index = 0; index < links.length; index++) {
        let $this = links[index];
        if(!$this.textContent.match(REreport)) continue;
        if ($this.mutated) continue;
        let commentLink = $this.querySelector('ul.flat-list a.comments,a[data-click-id="comments"]');
        if (!commentLink) continue;
        let link = commentLink.getAttribute('href');
        if ( link.substr(0,4) !== 'http' ) link = 'https://www.reddit.com' + link;
        link += '.json';
        getData(link, generateSelector($this)).then(commentBody => {
            if ( $this.querySelector('ul.flat-list') ) {
                let _li = document.createElement('li');
                let _a = document.createElement('button');
                _a.setAttribute('onclick', `openWindow(\`${commentBody}\`);`);
                _a.setAttribute('title', 'Check Reposterminator report comment');
                _a.innerHTML = 'View Reposterminator info';
                _li.appendChild(_a);
                $this.querySelector('ul.flat-list').appendChild(_li);
            } else if ( $this.querySelector('button[data-click-id="share"]') ) {
                let _li = document.createElement('div');
                let _a = document.createElement('button');
                _a.setAttribute('title', 'Check Reposterminator repost comment');
                _a.setAttribute('onclick', `openWindow(\`${commentBody}\`);`);
                _a.innerHTML = 'View Reposterminator info';
                _li.style.marginRight = '5px';
                _li.appendChild(_a);
                $this.querySelector('button[data-click-id="share"]').parentElement.insertAdjacentElement('afterend', _li);
            }
        });
        $this.mutated = true;
    }
}

(() => {
    let script = document.createElement('script');
    script.innerHTML = popupCreator;
    document.body.appendChild( script );
    setInterval(updatePosts, 3000);
    updatePosts();
})();

