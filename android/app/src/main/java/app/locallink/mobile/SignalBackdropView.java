package app.locallink.mobile;

import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Shader;
import android.view.View;
import android.view.animation.DecelerateInterpolator;

final class SignalBackdropView extends View {
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint line = new Paint(Paint.ANTI_ALIAS_FLAG);
    private ValueAnimator animator;
    private float phase;

    SignalBackdropView(Context context) {
        super(context);
        line.setStyle(Paint.Style.STROKE);
        line.setStrokeWidth(dp(1));
        if (ValueAnimator.areAnimatorsEnabled()) {
            animator = ValueAnimator.ofFloat(0f, 1f);
            animator.setDuration(12000);
            animator.setRepeatCount(ValueAnimator.INFINITE);
            animator.setRepeatMode(ValueAnimator.REVERSE);
            animator.setInterpolator(new DecelerateInterpolator());
            animator.addUpdateListener(value -> { phase = (float) value.getAnimatedValue(); invalidate(); });
            animator.start();
        }
    }

    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        int width=getWidth(),height=getHeight();
        paint.setShader(new LinearGradient(0,0,0,height,new int[]{Color.rgb(3,6,16),Color.rgb(7,16,31),Color.rgb(11,25,49),Color.rgb(5,9,20)},null,Shader.TileMode.CLAMP));
        canvas.drawRect(0,0,width,height,paint);paint.setShader(null);
        float horizon=height*(.56f-.025f*phase);
        paint.setShader(new LinearGradient(0,horizon-dp(120),0,horizon+dp(190),new int[]{Color.TRANSPARENT,Color.argb(70,44,91,190),Color.argb(30,239,155,180),Color.TRANSPARENT},null,Shader.TileMode.CLAMP));
        canvas.drawRect(0,horizon-dp(120),width,horizon+dp(190),paint);paint.setShader(null);
        line.setColor(Color.argb(55,120,165,255));
        RectF orbit=new RectF(-width*.12f,horizon-dp(100),width*1.12f,horizon+dp(170));
        canvas.drawOval(orbit,line);
        paint.setColor(Color.argb(175,94,231,215));
        float x=width*(.14f+.7f*phase),y=horizon+(float)Math.sin(phase*Math.PI*2)*dp(28);
        canvas.drawCircle(x,y,dp(3.5f),paint);
        paint.setColor(Color.argb(55,94,231,215));canvas.drawCircle(x,y,dp(16),paint);
    }

    @Override protected void onDetachedFromWindow(){if(animator!=null)animator.cancel();super.onDetachedFromWindow();}
    private float dp(float value){return value*getResources().getDisplayMetrics().density;}
}
