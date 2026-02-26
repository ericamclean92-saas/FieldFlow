import streamlit as st
import pandas as pd
from utils.supabase_client import supabase
from datetime import datetime, date
import io

st.set_page_config(page_title="LEM Management", layout="wide")
st.title("📑 LEM Management")

# --- Sidebar Filters ---
st.sidebar.header("🔍 Filter Options")

# Fetch Active Jobs
try:
    jobs_res = supabase.table("master_project").select("job_number, project_name").eq("status", "Active").execute()
    jobs = jobs_res.data if jobs_res.data else []
    job_opts = [j['job_number'] for j in jobs]
except:
    jobs = []
    job_opts = []

selected_job = st.sidebar.selectbox("Select Job #", job_opts)

# Date Range Filter
today = date.today()
start_date = st.sidebar.date_input("Start Date", date(today.year, today.month, 1))
end_date = st.sidebar.date_input("End Date", today)

# --- Tabs Configuration ---
tab_create, tab_manage = st.tabs(["📥 Ticket to LEM (Unbilled)", "QA/QC LEM Management (History)"])

# ==========================================
# [TAB 1] Ticket to LEM (Create New LEMs)
# ==========================================
with tab_create:
    st.subheader(f"📋 Available Tickets for LEM Generation [{selected_job}]")
    st.caption("Select field tickets to bundle into a single LEM.")

    if selected_job:
        try:
            # Query: Tickets for this Job + No LEM ID assigned (lem_id is null) + Within Date Range
            tickets_res = supabase.table("field_tickets")\
                .select("*")\
                .eq("job_number", selected_job)\
                .is_("lem_id", "null")\
                .gte("ticket_date", str(start_date))\
                .lte("ticket_date", str(end_date))\
                .order("ticket_date", desc=True)\
                .execute()
            
            tickets = tickets_res.data if tickets_res.data else []
        except Exception as e:
            st.error(f"Failed to load tickets: {e}")
            tickets = []

        if not tickets:
            st.info("No unassigned tickets found for this period. All tickets are already assigned to LEMs.")
        else:
            # Prepare DataFrame for Editor
            df_tickets = pd.DataFrame(tickets)
            df_tickets['Select'] = True  # Default to Select All
            
            # Show Data Editor
            edited_df = st.data_editor(
                df_tickets[["Select", "ticket_number", "ticket_date", "work_description", "status"]],
                column_config={
                    "Select": st.column_config.CheckboxColumn("Include?", default=True),
                    "ticket_number": "Ticket #",
                    "ticket_date": "Date",
                    "work_description": "Description",
                    "status": "Status"
                },
                hide_index=True,
                use_container_width=True
            )

            # Filter selected rows
            selected_rows = edited_df[edited_df["Select"] == True]
            
            st.divider()

            # --- Action Section: Generate LEM ---
            if not selected_rows.empty:
                st.markdown("### ⚙️ Generate LEM")
                st.caption(f"Selected **{len(selected_rows)}** tickets.")
                
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    # Auto-generate LEM Number Suggestion
                    # Format: LEM-JOB-YYMMDD-SEQ (Simplified for now)
                    suggestion = f"LEM-{selected_job}-{datetime.now().strftime('%y%m%d')}"
                    lem_number_input = st.text_input("LEM Number", value=suggestion, help="Unique identifier for this LEM.")
                
                with c2:
                    lem_date_input = st.date_input("LEM Date", date.today())

                with c3:
                    st.write("") # Spacer
                    st.write("")
                    create_btn = st.button("🚀 Create LEM", type="primary", use_container_width=True)

                if create_btn:
                    try:
                        # 1. Insert LEM Header
                        lem_data = {
                            "lem_number": lem_number_input,
                            "job_number": selected_job,
                            "lem_date": str(lem_date_input),
                            "period_start": str(start_date),
                            "period_end": str(end_date),
                            "status": "Generated" # Initial Status
                        }
                        lem_res = supabase.table("lems").insert(lem_data).execute()
                        new_lem_id = lem_res.data[0]['id']

                        # 2. Update Field Tickets (Link to LEM)
                        target_ticket_nums = selected_rows['ticket_number'].tolist()
                        
                        supabase.table("field_tickets")\
                            .update({"lem_id": new_lem_id, "status": "Invoiced"})\
                            .in_("ticket_number", target_ticket_nums)\
                            .execute()

                        st.success(f"✅ LEM [{lem_number_input}] created successfully!")
                        st.balloons()
                        st.rerun() # Refresh to move tickets from Tab 1 to Tab 2

                    except Exception as e:
                        st.error(f"Error creating LEM: {e}")
            else:
                st.warning("Please select at least one ticket to proceed.")

# ==========================================
# [TAB 2] LEM Management (History & Export)
# ==========================================
with tab_manage:
    st.subheader(f"📂 LEM History [{selected_job}]")
    st.caption("Review created LEMs and export to Excel for Accounting (Sage/Quickbooks).")

    try:
        # Fetch LEMs for the selected job
        if selected_job:
            lem_query = supabase.table("lems").select("*").eq("job_number", selected_job).order("created_at", desc=True)
        else:
            lem_query = supabase.table("lems").select("*").order("created_at", desc=True).limit(20)
            
        lem_list_res = lem_query.execute()
        lems = lem_list_res.data if lem_list_res.data else []

        if lems:
            for lem in lems:
                # Expandable Card for each LEM
                with st.expander(f"📄 {lem['lem_number']} | Date: {lem['lem_date']} | Status: {lem['status']}"):
                    
                    # Layout: Info & Export
                    col_info, col_export = st.columns([3, 1])
                    
                    with col_info:
                        st.markdown(f"**Period:** {lem['period_start']} to {lem['period_end']}")
                        
                        # Fetch Linked Tickets
                        linked_tickets = supabase.table("field_tickets")\
                            .select("ticket_number, ticket_date, work_description")\
                            .eq("lem_id", lem['id'])\
                            .execute()
                        
                        if linked_tickets.data:
                            st.dataframe(pd.DataFrame(linked_tickets.data), use_container_width=True, hide_index=True)
                        else:
                            st.warning("No tickets linked to this LEM.")

                    with col_export:
                        st.write("📤 **Actions**")
                        
                        # Excel Export Function
                        def to_excel(lem_data, tickets_data):
                            output = io.BytesIO()
                            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                                # Sheet 1: Summary
                                pd.DataFrame([lem_data]).to_excel(writer, sheet_name='LEM Summary', index=False)
                                # Sheet 2: Details
                                if tickets_data:
                                    pd.DataFrame(tickets_data).to_excel(writer, sheet_name='Tickets', index=False)
                            return output.getvalue()

                        excel_data = to_excel(lem, linked_tickets.data)
                        
                        st.download_button(
                            label="Download Excel",
                            data=excel_data,
                            file_name=f"{lem['lem_number']}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"btn_xls_{lem['id']}",
                            use_container_width=True
                        )
                        
                        # Status Toggle (Optional feature for later)
                        if lem['status'] == 'Generated':
                            if st.button("Mark as Approved", key=f"approve_{lem['id']}", use_container_width=True):
                                supabase.table("lems").update({"status": "Approved"}).eq("id", lem['id']).execute()
                                st.rerun()

        else:
            st.info("No LEMs found for the selected criteria.")

    except Exception as e:
        st.error(f"Error loading LEM history: {e}")
