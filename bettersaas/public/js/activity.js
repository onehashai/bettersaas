$(document).ready(function () {
    let interval = setInterval(function () {
        let timelineItem = document.querySelector('.timeline-item');

        if (timelineItem) {
            if (timelineItem.querySelector('.ai-generate-wrapper')) {
                clearInterval(interval);
                return;
            }

            let wrapper = document.createElement('div');
            wrapper.className = 'ai-generate-wrapper';

            let mainBtn = document.createElement('button');
            mainBtn.className = 'btn btn-xs btn-secondary action-btn ai-btn';
            mainBtn.innerHTML = `
                <i class="fa fa-star" style="margin-right: 4px;"></i>
                Ask AI
            `;
            let dropdown = document.createElement('div');
            dropdown.className = 'ai-generate-dropdown';

            let summarizeBtn = document.createElement('button');
            summarizeBtn.className = 'btn btn-xs btn-secondary ai-btn-options';
            summarizeBtn.innerHTML = `
                <i class="fa fa-list" style="margin-right: 4px;"></i>
                Summarize
            `;
            summarizeBtn.onclick = async () => {
                const doctype = frappe?.get_route()[1];
                const docname = frappe?.get_route()[2]; 

                const metadata = await fetchCommunications(doctype, docname);
                window.CRMCopilotWidget.open(); 
                window.CRMCopilotWidget.sendMessage('Summarize Conversations', metadata)
            }

            let writeEmailBtn = document.createElement('button');
            writeEmailBtn.className = 'btn btn-xs btn-secondary ai-btn-options';
            writeEmailBtn.innerHTML = `
                <i class="fa fa-envelope" style="margin-right: 4px;"></i>
                Write Email
            `;
            writeEmailBtn.onclick = () => {
                window.CRMCopilotWidget.open(); 
                window.CRMCopilotWidget.sendMessage('Write a mail')
            }

            dropdown.appendChild(summarizeBtn);
            dropdown.appendChild(writeEmailBtn);

            mainBtn.onclick = function (e) {
                e.stopPropagation();
                dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
            };

            document.addEventListener('click', function () {
                dropdown.style.display = 'none';
            });

            wrapper.appendChild(mainBtn);
            wrapper.appendChild(dropdown);
            timelineItem.appendChild(wrapper);

            clearInterval(interval);
        }
    }, 300);
});

async function fetchCommunications(doctype, docname) {
  const res = await fetch(`/api/method/bettersaas.bettersaas.utils.get_all_communications?doctype=${doctype}&docname=${docname}`);
  const data = await res.json();
  return data.message;
}