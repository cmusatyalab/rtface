package edu.cmu.cs.privacy_mediator;

import android.annotation.TargetApi;
import android.app.Dialog;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.Bundle;
import android.support.v4.app.Fragment;
import android.support.v7.app.AlertDialog;
import android.util.Log;
import android.view.Gravity;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.CompoundButton;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.Spinner;
import android.widget.SpinnerAdapter;
import android.widget.Switch;
import android.widget.TableLayout;
import android.widget.TableRow;
import android.widget.TextView;
import android.widget.Toast;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import edu.cmu.cs.gabriel.Const;
import edu.cmu.cs.gabriel.GabrielClientActivity;
import edu.cmu.cs.gabriel.GabrielConfigurationAsyncTask;

import static edu.cmu.cs.CustomExceptions.CustomExceptions.notifyError;

public class CloudletFragment extends Fragment implements CompoundButton.OnCheckedChangeListener {
    private final int LAUNCHCODE = 0;
    private static final int DLG_EXAMPLE1 = 0;
    private static final int TEXT_ID = 1000;
    public String inputDialogResult=null;
    private static final String TAG = "FaceSwapFragment";

    private List<PersonUIRow> personUIList = new ArrayList<PersonUIRow>();

    protected Button cloudletRunDemoButton;
    protected Button addPersonButton;
    protected Button uploadStateFromFileButton;
    protected Button uploadStateFromGoogleDriveButton;
    protected RadioGroup typeRadioGroup;
    protected RadioButton cloudletRadioButton;
    protected RadioButton cloudRadioButton;
    protected Spinner selectServerSpinner;
    protected EditText nameInput;

    protected View view;
    protected List<String> spinnerList;
    protected TableLayout tb;

    private static final String LOG_TAG = "fragment";

    public List<String> trainedPeople;
    public HashMap<String, String> faceTable;

    private PrivacyMediatorActivity getMyAcitivty() {
        PrivacyMediatorActivity a = (PrivacyMediatorActivity) getActivity();
        return a;
    }

    @TargetApi(Build.VERSION_CODES.M)
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        this.spinnerList = new ArrayList<String>();
        faceTable = new HashMap<String, String>();
        trainedPeople = new ArrayList<String>();
    }

    @Override
    public void onResume(){
        super.onResume();
        Log.d(TAG, "on resume");
        if (getMyAcitivty().onResumeFromLoadState){
            Log.d(TAG, "on resume from load state. don't refresh yet");
            getMyAcitivty().onResumeFromLoadState=false;
        }
    }

    @Override
    public View onCreateView(LayoutInflater inflater, ViewGroup container,
                             Bundle savedInstanceState) {
        super.onCreateView(inflater, container, savedInstanceState);
        view=inflater.inflate(R.layout.unified_fragment,container,false);

        nameInput=(EditText)view.findViewById(R.id.name_input);
        addPersonButton = (Button)view.findViewById(R.id.addPersonButton);
        uploadStateFromFileButton = (Button)view.findViewById(R.id.uploadFromFileButton);
        uploadStateFromGoogleDriveButton =
                (Button)view.findViewById(R.id.uploadFromGoogleDriveButton);

//        cloudletRunDemoButton.setOnClickListener(new Button.OnClickListener() {
//            @Override
//            public void onClick(View v) {
//                Const.GABRIEL_IP = getMyAcitivty().currentServerIp;
//                Intent intent = new Intent(getContext(), GabrielClientActivity.class);
//                intent.putExtra("faceTable", faceTable);
//                startActivity(intent);
//                Toast.makeText(getContext(), "initializing demo", Toast.LENGTH_SHORT).show();
//            }
//        });

        addPersonButton.setOnClickListener(new Button.OnClickListener() {
            @Override
            public void onClick(View v) {
                String name = nameInput.getText().toString();
                if ((name == null) || (name.isEmpty())){
                    notifyError("Please Enter a valid name",
                            new DialogInterface.OnClickListener() {
                        @Override
                        public void onClick(DialogInterface dialog, int which) {
                        }
                    }, getActivity());
                }
                launchTrainingActivity(name);
            }
        });

        uploadStateFromFileButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                getMyAcitivty().actionUploadStateFromLocalFile();
            }
        });

        uploadStateFromGoogleDriveButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                getMyAcitivty().actionReadStateFileFromGoogleDrive();
            }
        });

        return view;
    }

    private void launchTrainingActivity(String name){
        if (checkName(name)) {
            Log.d(TAG, name);
            trainedPeople.add(name);
            Log.d(TAG, "add name :" + name);
            //get ip from preference
            startGabrielActivityForTraining(name, Const.CLOUDLET_GABRIEL_IP);
        }
    }


    @Override
    public void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
    }



    protected boolean checkName(String name){
        if (null == name || name.isEmpty()){
            new AlertDialog.Builder(getContext())
                    .setTitle("Invalid")
                    .setMessage("Please Enter a Valid Name")
                    .setPositiveButton(android.R.string.yes, new DialogInterface.OnClickListener() {
                        public void onClick(DialogInterface dialog, int which) {
                            // do nothing
                        }
                    })
                    .setIcon(android.R.drawable.ic_dialog_alert)
                    .show();
            return false;
        }

        if (trainedPeople.contains(name)){
            new AlertDialog.Builder(getContext())
                    .setTitle("Duplicate")
                    .setMessage("Duplicate Name Entered")
                    .setPositiveButton(android.R.string.yes, new DialogInterface.OnClickListener() {
                        public void onClick(DialogInterface dialog, int which) {
                        }
                    })
                    .setIcon(android.R.drawable.ic_dialog_alert)
                    .show();
            return false;
        }

        return true;
    }



    private String stripQuote(String input){
        String output = input.replaceAll("^\"|\"$", "");
        return output;
    }


    private void startGabrielActivityForTraining(String name, String ip) {
        //TODO: how to handle sync faces between cloud and cloudlet?
        Const.GABRIEL_IP = ip;
        Intent intent = new Intent(getContext(), GabrielClientActivity.class);
        intent.putExtra("name", name);
        startActivityForResult(intent, LAUNCHCODE);
        Toast.makeText(getContext(), "training", Toast.LENGTH_SHORT).show();
    }


    private String chosen = null;

    @Override
    public void onCheckedChanged(final CompoundButton buttonView, boolean isChecked) {
        PersonUIRow searchUIRow=null;
        for (PersonUIRow uiRow : personUIList) {
            if (uiRow.switchView == buttonView) {
                searchUIRow=uiRow;
                break;
            }
        }
        final PersonUIRow curUIRow = searchUIRow;
        String curName=curUIRow.nameView.getText().toString();
        if (isChecked){
            AlertDialog.Builder builder = new AlertDialog.Builder(getContext());
            builder.setTitle("Make your selection");
//            ArrayList<String> copyTrainedPeople = new ArrayList<String>(trainedPeople);
//            copyTrainedPeople.remove(curUIRow.nameView.getText());
            final String[] itemArray= new String[trainedPeople.size()-1];
            int idx=0;
            for (String name:trainedPeople){
                if (!name.equals(curName)){
                    itemArray[idx]=name;
                    idx++;
                }
            }
//            trainedPeople.toArray(itemArray);

            builder.setItems(itemArray, new DialogInterface.OnClickListener() {
                public void onClick(DialogInterface dialog, int item) {
//                    PersonUIRow curUIRow = null;
//                    for (PersonUIRow uiRow : personUIList) {
//                        if (uiRow.switchView == buttonView) {
//                            curUIRow = uiRow;
//                            break;
//                        }
//                    }

                    // Do something with the selection
                    chosen = itemArray[item];
                    if (chosen.equals(curUIRow.nameView.getText())) {
                        curUIRow.switchView.setChecked(false);
                        return;
                    }
                    curUIRow.subView.setText(chosen);
                    curUIRow.subView.setVisibility(View.VISIBLE);
                    faceTable.put((String) curUIRow.nameView.getText(), chosen);
                    Log.d(TAG, "chose to be substitute: " + chosen);
                    return;
                }
            });
            AlertDialog alert = builder.create();
            alert.setCanceledOnTouchOutside(false);
            alert.setOnCancelListener(new DialogInterface.OnCancelListener() {
                @Override
                public void onCancel(DialogInterface dialog) {
                    curUIRow.switchView.setChecked(false);
                }
            });
            alert.show();
        } else {
            curUIRow.subView.setText("");
            curUIRow.subView.setVisibility(View.INVISIBLE);
            faceTable.remove(curUIRow.nameView.getText());
        }
    }

    public void clearPersonTable(){
        if (null != trainedPeople){
            trainedPeople.clear();
            for (PersonUIRow uiRow: personUIList){
                tb.removeView(uiRow.tr);
            }
        }
    }
}
