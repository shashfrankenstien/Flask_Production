Number.prototype.pad = function(size) {
    let s = String(this);
    while (s.length < (size || 2)) {s = "0" + s;}
    return s;
}

function countdown_str(seconds) {
    let hours = Math.floor(seconds / (60*60))
    seconds -= hours * (60*60)
    let minutes = Math.floor(seconds / 60)
    seconds -= minutes * 60
    return `${hours.pad()}:${minutes.pad()}:${Math.floor(seconds).pad()}`
}

// update modal theme to use theme from page

const MODAL_TRANSITION_START = {top: '-5%', left: '-5%'}

for (let _modal of [modal_alert, modal_prompt, modal_confirm]) {
    _modal.container.classList.add('console-color')
    _modal.transitionStartPos = MODAL_TRANSITION_START
}


// setup rerun popup modal
const _RERUN_POPUP_ELEM = document.getElementById('rerun-popup')
let _rerun_height = "" // disable fixed height by default
let _rerun_width = "40rem"
if (_RERUN_POPUP_ELEM.querySelectorAll(".rerun-kwarg").length > 6) {
    _rerun_height = "35rem" // cap it from getting too big
}
if (_RERUN_POPUP_ELEM.querySelectorAll(".rerun-kwarg").length > 0) {
    _rerun_width = "50rem" // cap it from getting too big
}


const RERUN_MODAL = new Modal(_RERUN_POPUP_ELEM,
{
    width: _rerun_width,
    height: _rerun_height,
    displayStyle: 'flex',
    containerColor: 'transparent',
    transitionStartPos: MODAL_TRANSITION_START
})


function rerun_trigger(job_name, jobid) {
    RERUN_MODAL.open().then(popup=>{
        let job_name_prompt = popup.querySelector("#popup-rerun-prompt")
        job_name_prompt.focus()

        popup.querySelectorAll(".none-btn").forEach(btn=>{
            const editable = btn.parentElement.hasAttribute('data-type') // has an editable type
            const inp = btn.parentElement.querySelector("input, select, textarea")

            if (btn.hasAttribute('data-none') && editable) {
                inp.setAttribute("disabled", "disabled")
            }

            btn.onclick = () => {
                const checked = btn.getAttribute("data-none")
                if (checked===null) {
                    btn.setAttribute("data-none", '1')
                    if (editable) {
                        inp.setAttribute("disabled", "disabled")
                    }
                } else {
                    btn.removeAttribute('data-none')
                    if (editable) {
                        inp.removeAttribute("disabled")
                    }
                }
            }
        })

        popup.querySelector("#popup-cancel-btn").onclick = ()=>{
            RERUN_MODAL.close()
        }

        popup.querySelector("#popup-rerun-btn").onclick = ()=>{ // assign rerun button action
            let updated_kwargs = {}
            let updated_types = {}
            for (let kwarg of popup.querySelectorAll(".rerun-kwarg")) {
                const name = kwarg.getAttribute('data-key')
                const inp_elem = kwarg.querySelector("input, select, textarea")
                const new_val = inp_elem.value
                const orig_value = kwarg.getAttribute('data-value')
                const none_btn = kwarg.querySelector(".none-btn")
                const none_value = none_btn.hasAttribute('data-none')
                const orig_none_value = none_btn.hasAttribute('data-orig-none')
                if (none_value) {
                    if (!orig_none_value) {
                        console.log("updated", name, "None")
                        updated_kwargs[name] = null
                        updated_types[name] = 'none' // inform the backend that the value is None
                    }
                }
                else if ((!inp_elem.disabled) && (orig_value !== new_val)) {
                    const normalized_orig = String(orig_value ?? '').replace(/\r\n/g, '\n').trim()
                    const normalized_new = String(new_val ?? '').replace(/\r\n/g, '\n').trim()
                    if (normalized_orig !== normalized_new) {
                        console.log("updated", orig_value, new_val)
                        updated_kwargs[name] = new_val
                        updated_types[name] = kwarg.getAttribute('data-type')
                    }
                }
            }

            let job_name_text = job_name_prompt.value
            console.log(job_name, jobid, updated_kwargs, job_name_text)
            if (job_name_text == job_name) {
                if (Object.keys(updated_kwargs).length > 0) {
                    modal_confirm.open(
                        "Some arguments were changed. Are you sure you want to rerun?",
                        ()=>send_rerun_request(jobid, updated_kwargs, updated_types)
                    )
                } else {
                    send_rerun_request(jobid, updated_kwargs, updated_types)
                }
            } else {
                modal_alert.open("Rerun aborted")
            }
            RERUN_MODAL.close()
        }
    })
}


function send_rerun_request(jobid, kwargs, types) {
    const payload = {jobid, kwargs, types, api_token: API_TOKEN}
    fetch('./rerun', {method: 'POST', body: JSON.stringify(payload)}).then(resp => {
        return resp.json();
    }).then(j=>{
        if (j.success)
            window.location.reload()
        else if (j.error)
            throw Error(j.error)
        else
            throw Error("Rerun failed")
    }).catch(e=>modal_alert.open(e))
}


function enable_disable(job_name, jobid, disable) {
    const prompt_txt = "Please type in the job name to confirm " + ((disable) ? "disable": "enable")
    // const input_txt = prompt(prompt_txt, "");

    const on_disable = (input_txt) => {
        const payload = {jobid, disable, api_token: API_TOKEN}
        if (input_txt===job_name) {
            fetch('./enable_disable', {method: 'POST', body: JSON.stringify(payload)}).then(resp => {
                return resp.json();
            }).then(j=>{
                if (j.success)
                    window.location.reload()
                else if (j.error)
                    throw Error(j.error)
                else
                    throw Error("Action failed")
            }).catch(e=>modal_alert.open(e))
        } else {
            modal_alert.open("Action aborted")
        }
    }

    modal_prompt.open(prompt_txt, on_disable)
}


window.addEventListener('load', (event) => {
    //scroll to bottom
    document.getElementsByClassName("log_table")[0].querySelectorAll("div").forEach(d=>d.scrollTo(0,d.scrollHeight))
    if (RUNNING) {
        setTimeout(()=>location.reload(), TASKPAGE_REFRESH * 1000)
    } else if ( isNaN(NEXT_RUN) ) { // if not number
        document.getElementById("next-run-in").innerHTML = NEXT_RUN
    } else if (SCHED_HAS_CHECKED) { // if scheduler is actively checking, running and rescheduling jobs
        const timer = setInterval(()=>{
            const time_to_run = (NEXT_RUN * 1000)-Date.now()
            if (time_to_run <= 0) {
                clearInterval(timer)
                setTimeout(()=>location.reload(), 1000) // small timeout to avoid too many reloads
            } else {
                document.getElementById("next-run-in").innerHTML = countdown_str(time_to_run/1000)
            }
        }, 1000)
    }
    //highlight error line
    if (ERR_LINE>=0) {
        hljs.initHighlightLinesOnLoad([
            [{start: ERR_LINE, end: ERR_LINE, color: 'rgba(255, 0, 0, 0.4)'}], // Highlight some lines in the first code block.
        ]);
    }
});
