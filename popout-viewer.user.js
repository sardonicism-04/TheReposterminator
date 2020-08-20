// ==UserScript==
// @name           Repost comment viewer
// @description    Quickly view TheReposterminator's comments
// @author         sardonicism-04
// @run-at         document-idle
// @include        https://www.reddit.com/*
// @include        https://old.reddit.com/*
// ==/UserScript==

const REuslash = /\/u\/.*/;
// ^ Filter usernames for image displaying
const REpost = /https\:\/\/redd\.it\/.*/;
// ^ Filter submission links for image displaying
const REreport = /TheReposterminator\: Possible repost \( \d*? matches \| \d*? removed\/deleted \)/;
// ^ Pick out right posts to add buttons to
const injectedJS = `
const injectCSS = (styleString, targetWindow) => {
    const style = targetWindow.document.createElement('style');
    style.textContent = styleString;
    targetWindow.document.head.append(style);
}
const openWindow = (content) => {
    let popup = window.open("", null, "height=600,width=1000,status=yes,toolbar=no,menubar=no,location=no");

    injectCSS(\`
        table, th, td {
          border: 1px solid black;
          border-collapse: collapse;
        }
        * {
            font-family: 'sans-serif';
        }\`,
        popup
    ); // inject some CSS to make the table look nice

    popup.document.body.innerHTML = content; // Inject the table's HTML

    for (let link of popup.document.links) { // Display the images below the table
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
// ^ Inject JavaScript into document to allow for popup creation

const getData = async (urlString) => {
    let url = new URL(urlString);
    url.search = '';
    let resp = await fetch( // Get the JSON for the URL
        url, {method: 'GET'});
    let data = await resp.json();
    for (let comment_raw of data[1].data.children) {

        let comment = comment_raw.data
        if (comment.author === 'TheReposterminator') { // Get the right comment
            return comment.body_html.replace(/&lt;/g, '<').replace(/&gt;/g, '>');
        }   // ^ Transform the string to be valid HTML
    }
}

const updatePosts = () => { // Apply buttons to posts
    if (document.readyState !== 'complete') return; // Wait until we're ready
    for (let post of document.querySelectorAll('.linklisting .link,div.Post')) {

        let commentLink = post.querySelector('ul.flat-list a.comments,a[data-click-id="comments"]');
        if (!post.textContent.match(REreport) || post.mutated || !commentLink) continue; // Should we skip?

        let link = commentLink.getAttribute('href');
        if (link.substr(0,4) !== 'http') link = 'https://www.reddit.com' + link;
        link += '.json'; // Prepare URL for fetching

        getData(link).then(commentBody => {

            let infoButton = document.createElement('button'); // Create and modify the button element
            infoButton.setAttribute('onclick', `openWindow(\`${commentBody}\`);`);
            infoButton.setAttribute('title', 'Check Reposterminator report comment');
            infoButton.innerHTML = 'View Reposterminator info';

            if (post.querySelector('ul.flat-list')) {

                let buttonContainer = document.createElement('li');
                buttonContainer.appendChild(infoButton);
                post.querySelector('ul.flat-list').appendChild(buttonContainer);
            } else if (post.querySelector('button[data-click-id="share"]')) {

                let buttonContainer = document.createElement('div');
                buttonContainer.style.marginRight = '5px';
                buttonContainer.appendChild(infoButton);
                post.querySelector('button[data-click-id="share"]').parentElement
                    .insertAdjacentElement('afterend', buttonContainer);
            } // Append the button to the document, one way or another
        });
        post.mutated = true; // We don't need to mutate this one again
    }
}

(() => {
    let script = document.createElement('script');
    script.innerHTML = injectedJS;
    document.body.appendChild(script); // Inject our popup creator code

    setInterval(updatePosts, 3000); // Keep an eye on posts and add buttons when needed
    updatePosts();
})();

